// _worker.js
import { connect } from "cloudflare:sockets";
var userID = "6e6cb97e-57ac-4e8f-ad90-2b2fbb21bc45";
var proxyIP = "";
var hostnames = "";

if (!isValidUUID(userID)) {
  throw new Error("uuid is not valid");
}
var worker_default = {
  /**
   * @param {import("@cloudflare/workers-types").Request} request
   * @param {{UUID: string, PROXYIP: string}} env
   * @param {import("@cloudflare/workers-types").ExecutionContext} ctx
   * @returns {Promise<Response>}
   */
  async fetch(request, env, ctx) {
    try {
      userID = env.uuid || userID;
      proxyIP = env.PROXYIP || proxyIP;
      const upgradeHeader = request.headers.get("Upgrade");
      if (!upgradeHeader || upgradeHeader !== "websocket") {
        const url = new URL(request.url);
        switch (url.pathname) {
          case "/cf":
            return new Response(JSON.stringify(request.cf, null, 4), {
              status: 200,
              headers: {
                "Content-Type": "application/json;charset=utf-8"
              }
            });
          case `/geo`:
            {
              const vlessConfig = await getVLESSConfig(userID, request.headers.get("Host"), proxyIP);
              return new Response(`${vlessConfig}`, {
                status: 200,
                headers: {
                  "Content-Type": "text/html; charset=utf-8"
                }
              });
            }
            ;
          default:
            const randomHostname = hostnames[Math.floor(Math.random() * hostnames.length)];
            const newHeaders = new Headers(request.headers);
            newHeaders.set("cf-connecting-ip", "1.2.3.4");
            newHeaders.set("x-forwarded-for", "1.2.3.4");
            newHeaders.set("x-real-ip", "1.2.3.4");
            newHeaders.set("referer", "https://www.google.com/search?q=edtunnel");
            const proxyUrl = "https://" + randomHostname + url.pathname + url.search;
            let modifiedRequest = new Request(proxyUrl, {
              method: request.method,
              headers: newHeaders,
              body: request.body,
              redirect: "manual"
            });
            const proxyResponse = await fetch(modifiedRequest, { redirect: "manual" });
            if ([301, 302].includes(proxyResponse.status)) {
              return new Response(`Redirects to ${randomHostname} are not allowed.`, {
                status: 403,
                statusText: "Forbidden"
              });
            }
            return proxyResponse;
        }
      } else {
        return await vlessOverWSHandler(request);
      }
    } catch (err) {
      let e = err;
      return new Response(e.toString());
    }
  }
};
async function vlessOverWSHandler(request) {
  const webSocketPair = new WebSocketPair();
  const [client, webSocket] = Object.values(webSocketPair);
  webSocket.accept();
  let address = "";
  let portWithRandomLog = "";
  const log = (info, event) => {
    console.log(`[${address}:${portWithRandomLog}] ${info}`, event || "");
  };
  const earlyDataHeader = request.headers.get("sec-websocket-protocol") || "";
  const readableWebSocketStream = makeReadableWebSocketStream(webSocket, earlyDataHeader, log);
  let remoteSocketWapper = {
    value: null
  };
  let udpStreamWrite = null;
  let isDns = false;
  readableWebSocketStream.pipeTo(new WritableStream({
    async write(chunk, controller) {
      if (isDns && udpStreamWrite) {
        return udpStreamWrite(chunk);
      }
      if (remoteSocketWapper.value) {
        const writer = remoteSocketWapper.value.writable.getWriter();
        await writer.write(chunk);
        writer.releaseLock();
        return;
      }
      const {
        hasError,
        message,
        portRemote = 443,
        addressRemote = "",
        rawDataIndex,
        vlessVersion = new Uint8Array([0, 0]),
        isUDP
      } = processVlessHeader(chunk, userID);
      address = addressRemote;
      portWithRandomLog = `${portRemote}--${Math.random()} ${isUDP ? "udp " : "tcp "} `;
      if (hasError) {
        throw new Error(message);
        return;
      }
      if (isUDP) {
        if (portRemote === 53) {
          isDns = true;
        } else {
          throw new Error("UDP proxy only enable for DNS which is port 53");
          return;
        }
      }
      const vlessResponseHeader = new Uint8Array([vlessVersion[0], 0]);
      const rawClientData = chunk.slice(rawDataIndex);
      if (isDns) {
        const { write } = await handleUDPOutBound(webSocket, vlessResponseHeader, log);
        udpStreamWrite = write;
        udpStreamWrite(rawClientData);
        return;
      }
      handleTCPOutBound(remoteSocketWapper, addressRemote, portRemote, rawClientData, webSocket, vlessResponseHeader, log);
    },
    close() {
      log(`readableWebSocketStream is close`);
    },
    abort(reason) {
      log(`readableWebSocketStream is abort`, JSON.stringify(reason));
    }
  })).catch((err) => {
    log("readableWebSocketStream pipeTo error", err);
  });
  return new Response(null, {
    status: 101,
    // @ts-ignore
    webSocket: client
  });
}
async function handleTCPOutBound(remoteSocket, addressRemote, portRemote, rawClientData, webSocket, vlessResponseHeader, log) {
  async function connectAndWrite(address, port) {
    const tcpSocket2 = connect({
      hostname: address,
      port
    });
    remoteSocket.value = tcpSocket2;
    log(`connected to ${address}:${port}`);
    const writer = tcpSocket2.writable.getWriter();
    await writer.write(rawClientData);
    writer.releaseLock();
    return tcpSocket2;
  }
  async function retry() {
    const tcpSocket2 = await connectAndWrite(proxyIP || addressRemote, portRemote);
    tcpSocket2.closed.catch((error) => {
      console.log("retry tcpSocket closed error", error);
    }).finally(() => {
      safeCloseWebSocket(webSocket);
    });
    remoteSocketToWS(tcpSocket2, webSocket, vlessResponseHeader, null, log);
  }
  const tcpSocket = await connectAndWrite(addressRemote, portRemote);
  remoteSocketToWS(tcpSocket, webSocket, vlessResponseHeader, retry, log);
}
function makeReadableWebSocketStream(webSocketServer, earlyDataHeader, log) {
  let readableStreamCancel = false;
  const stream = new ReadableStream({
    start(controller) {
      webSocketServer.addEventListener("message", (event) => {
        if (readableStreamCancel) {
          return;
        }
        const message = event.data;
        controller.enqueue(message);
      });
      webSocketServer.addEventListener(
        "close",
        () => {
          safeCloseWebSocket(webSocketServer);
          if (readableStreamCancel) {
            return;
          }
          controller.close();
        }
      );
      webSocketServer.addEventListener(
        "error",
        (err) => {
          log("webSocketServer has error");
          controller.error(err);
        }
      );
      const { earlyData, error } = base64ToArrayBuffer(earlyDataHeader);
      if (error) {
        controller.error(error);
      } else if (earlyData) {
        controller.enqueue(earlyData);
      }
    },
    pull(controller) {
    },
    cancel(reason) {
      if (readableStreamCancel) {
        return;
      }
      log(`ReadableStream was canceled, due to ${reason}`);
      readableStreamCancel = true;
      safeCloseWebSocket(webSocketServer);
    }
  });
  return stream;
}
function processVlessHeader(vlessBuffer, userID2) {
  if (vlessBuffer.byteLength < 24) {
    return {
      hasError: true,
      message: "invalid data"
    };
  }
  const version = new Uint8Array(vlessBuffer.slice(0, 1));
  let isValidUser = false;
  let isUDP = false;
  if (stringify(new Uint8Array(vlessBuffer.slice(1, 17))) === userID2) {
    isValidUser = true;
  }
  if (!isValidUser) {
    return {
      hasError: true,
      message: "invalid user"
    };
  }
  const optLength = new Uint8Array(vlessBuffer.slice(17, 18))[0];
  const command = new Uint8Array(
    vlessBuffer.slice(18 + optLength, 18 + optLength + 1)
  )[0];
  if (command === 1) {
  } else if (command === 2) {
    isUDP = true;
  } else {
    return {
      hasError: true,
      message: `command ${command} is not support, command 01-tcp,02-udp,03-mux`
    };
  }
  const portIndex = 18 + optLength + 1;
  const portBuffer = vlessBuffer.slice(portIndex, portIndex + 2);
  const portRemote = new DataView(portBuffer).getUint16(0);
  let addressIndex = portIndex + 2;
  const addressBuffer = new Uint8Array(
    vlessBuffer.slice(addressIndex, addressIndex + 1)
  );
  const addressType = addressBuffer[0];
  let addressLength = 0;
  let addressValueIndex = addressIndex + 1;
  let addressValue = "";
  switch (addressType) {
    case 1:
      addressLength = 4;
      addressValue = new Uint8Array(
        vlessBuffer.slice(addressValueIndex, addressValueIndex + addressLength)
      ).join(".");
      break;
    case 2:
      addressLength = new Uint8Array(
        vlessBuffer.slice(addressValueIndex, addressValueIndex + 1)
      )[0];
      addressValueIndex += 1;
      addressValue = new TextDecoder().decode(
        vlessBuffer.slice(addressValueIndex, addressValueIndex + addressLength)
      );
      break;
    case 3:
      addressLength = 16;
      const dataView = new DataView(
        vlessBuffer.slice(addressValueIndex, addressValueIndex + addressLength)
      );
      const ipv6 = [];
      for (let i = 0; i < 8; i++) {
        ipv6.push(dataView.getUint16(i * 2).toString(16));
      }
      addressValue = ipv6.join(":");
      break;
    default:
      return {
        hasError: true,
        message: `invild  addressType is ${addressType}`
      };
  }
  if (!addressValue) {
    return {
      hasError: true,
      message: `addressValue is empty, addressType is ${addressType}`
    };
  }
  return {
    hasError: false,
    addressRemote: addressValue,
    addressType,
    portRemote,
    rawDataIndex: addressValueIndex + addressLength,
    vlessVersion: version,
    isUDP
  };
}
async function remoteSocketToWS(remoteSocket, webSocket, vlessResponseHeader, retry, log) {
  let remoteChunkCount = 0;
  let chunks = [];
  let vlessHeader = vlessResponseHeader;
  let hasIncomingData = false;
  await remoteSocket.readable.pipeTo(
    new WritableStream({
      start() {
      },
      /**
       * 
       * @param {Uint8Array} chunk 
       * @param {*} controller 
       */
      async write(chunk, controller) {
        hasIncomingData = true;
        if (webSocket.readyState !== WS_READY_STATE_OPEN) {
          controller.error(
            "webSocket.readyState is not open, maybe close"
          );
        }
        if (vlessHeader) {
          webSocket.send(await new Blob([vlessHeader, chunk]).arrayBuffer());
          vlessHeader = null;
        } else {
          webSocket.send(chunk);
        }
      },
      close() {
        log(`remoteConnection!.readable is close with hasIncomingData is ${hasIncomingData}`);
      },
      abort(reason) {
        console.error(`remoteConnection!.readable abort`, reason);
      }
    })
  ).catch((error) => {
    console.error(
      `remoteSocketToWS has exception `,
      error.stack || error
    );
    safeCloseWebSocket(webSocket);
  });
  if (hasIncomingData === false && retry) {
    log(`retry`);
    retry();
  }
}
function base64ToArrayBuffer(base64Str) {
  if (!base64Str) {
    return { error: null };
  }
  try {
    base64Str = base64Str.replace(/-/g, "+").replace(/_/g, "/");
    const decode = atob(base64Str);
    const arryBuffer = Uint8Array.from(decode, (c) => c.charCodeAt(0));
    return { earlyData: arryBuffer.buffer, error: null };
  } catch (error) {
    return { error };
  }
}
function isValidUUID(uuid) {
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[4][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  return uuidRegex.test(uuid);
}
var WS_READY_STATE_OPEN = 1;
var WS_READY_STATE_CLOSING = 2;
function safeCloseWebSocket(socket) {
  try {
    if (socket.readyState === WS_READY_STATE_OPEN || socket.readyState === WS_READY_STATE_CLOSING) {
      socket.close();
    }
  } catch (error) {
    console.error("safeCloseWebSocket error", error);
  }
}
var byteToHex = [];
for (let i = 0; i < 256; ++i) {
  byteToHex.push((i + 256).toString(16).slice(1));
}
function unsafeStringify(arr, offset = 0) {
  return (byteToHex[arr[offset + 0]] + byteToHex[arr[offset + 1]] + byteToHex[arr[offset + 2]] + byteToHex[arr[offset + 3]] + "-" + byteToHex[arr[offset + 4]] + byteToHex[arr[offset + 5]] + "-" + byteToHex[arr[offset + 6]] + byteToHex[arr[offset + 7]] + "-" + byteToHex[arr[offset + 8]] + byteToHex[arr[offset + 9]] + "-" + byteToHex[arr[offset + 10]] + byteToHex[arr[offset + 11]] + byteToHex[arr[offset + 12]] + byteToHex[arr[offset + 13]] + byteToHex[arr[offset + 14]] + byteToHex[arr[offset + 15]]).toLowerCase();
}
function stringify(arr, offset = 0) {
  const uuid = unsafeStringify(arr, offset);
  if (!isValidUUID(uuid)) {
    throw TypeError("Stringified UUID is invalid");
  }
  return uuid;
}
async function handleUDPOutBound(webSocket, vlessResponseHeader, log) {
  let isVlessHeaderSent = false;
  const transformStream = new TransformStream({
    start(controller) {
    },
    transform(chunk, controller) {
      for (let index = 0; index < chunk.byteLength; ) {
        const lengthBuffer = chunk.slice(index, index + 2);
        const udpPakcetLength = new DataView(lengthBuffer).getUint16(0);
        const udpData = new Uint8Array(
          chunk.slice(index + 2, index + 2 + udpPakcetLength)
        );
        index = index + 2 + udpPakcetLength;
        controller.enqueue(udpData);
      }
    },
    flush(controller) {
    }
  });
  transformStream.readable.pipeTo(new WritableStream({
    async write(chunk) {
      const resp = await fetch(
        "https://1.1.1.1/dns-query",
        {
          method: "POST",
          headers: {
            "content-type": "application/dns-message"
          },
          body: chunk
        }
      );
      const dnsQueryResult = await resp.arrayBuffer();
      const udpSize = dnsQueryResult.byteLength;
      const udpSizeBuffer = new Uint8Array([udpSize >> 8 & 255, udpSize & 255]);
      if (webSocket.readyState === WS_READY_STATE_OPEN) {
        log(`doh success and dns message length is ${udpSize}`);
        if (isVlessHeaderSent) {
          webSocket.send(await new Blob([udpSizeBuffer, dnsQueryResult]).arrayBuffer());
        } else {
          webSocket.send(await new Blob([vlessResponseHeader, udpSizeBuffer, dnsQueryResult]).arrayBuffer());
          isVlessHeaderSent = true;
        }
      }
    }
  })).catch((error) => {
    log("dns udp has error" + error);
  });
  const writer = transformStream.writable.getWriter();
  return {
    /**
     * 
     * @param {Uint8Array} chunk 
     */
    write(chunk) {
      writer.write(chunk);
    }
  };
}
async function getVLESSConfig(userID2, hostName, proxyIP2) {
  try {
        const response = await fetch(`https://ipcf.geol.my.id/?ip=${proxyIP}&api_key=geo`);
    const data = await response.json();
    const proxyip = data.proxyStatus;
    const ip = data.ip;
    const isp = data.isp;
    const country = data.country;
    const city = data.city;
    const vlessTls = `vless://${userID2}@${hostName}:443?encryption=none&security=tls&sni=${hostName}&fp=randomized&type=ws&host=${hostName}&path=%2Fvless-ws#${isp}`;
    const vlessNtls = `vless://${userID2}@${hostName}:80?path=%2Fvless-ws&security=none&encryption=none&host=${hostName}&fp=randomized&type=ws&sni=${hostName}#${isp}`;
    const vlessTlsFormatted = vlessTls.replace(/ /g, "+");
    const vlessNtlsFormatted = vlessNtls.replace(/ /g, "+");
    return `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GEO-PROJECT</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
    <style>
        body {
            font-family: 'Verdana', sans-serif;
            background: url('https://raw.githubusercontent.com/jaka2m/mau/kepo/assets/img/1.jpg') no-repeat center center fixed;
            background-size: cover;
            color: #f1f1f1;
            display: flex;
            flex-direction: column;
            align-items: center;
            height: 100vh;
            margin: 0;
            padding: 20px;
            box-sizing: border-box;
            transition: background 0.5s ease, color 0.5s ease;
        }

        .dark-theme {
            background: #121212;
            color: #e0e0e0;
        }

        .dark-theme .container {
            background-color: rgba(51, 51, 51, 0.9);
        }

        .dark-theme button {
            background-color: rgba(30, 143, 255, 0.5);
        }

        .dark-theme .social-links a {
            color: #e0e0e0;
        }

        h1 {
            font-size: 6em;
            color: #ff7900;
            font-weight: bold;
            animation: fadeInOut 3s ease-in-out infinite;
            text-align: center;
            margin: 20px 0;
        }

        .word {
            display: inline-block;
            font-size: 0.8em;
            position: relative;
            font-weight: bold;
        }

        .superscript {
            font-size: 0.5em;
            position: absolute;
            top: -0.5em;
            right: -0.3em;
        }

        @keyframes fadeInOut {
            0% { opacity: 0; transform: translateY(-20px); }
            50% { opacity: 1; transform: translateY(0); }
            100% { opacity: 0; transform: translateY(20px); }
        }

        .container {
            text-align: center;
            background-color: rgba(51, 51, 51, 0.685);
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.5);
            width: 600px;
            max-width: 90%;
        }

        .info {
            margin: 10px 0;
            background-color: #444444a6;
            padding: 20px;
            border-radius: 8px;
            text-align: left;
            font-family: 'Verdana', sans-serif;
            animation: slideIn 1s ease-out;
            overflow-x: auto;
        }

        @keyframes slideIn {
            from { opacity: 0; transform: translateX(100%); }
            to { opacity: 1; transform: translateX(0); }
        }

        .pinfo {
            word-break: break-all;
            overflow-wrap: break-word;
            font-size: 14px;
            padding: 0 40px;
            margin: 0;
        }

        h2 {
            margin: 10px 0;
            font-size: 1.5em;
            color: #ff7900;
            font-weight: bold;
            font-family: 'Montserrat', sans-serif;
        }

        .hello {
            font-size: 14px;
            font-family: 'Verdana', sans-serif;
        }

        .github-link {
            color: #1e90ff;
            text-decoration: none;
            font-weight: bold;
        }

        .text-section {
            margin: 10px 0;
            background-color: #444444a6;
            padding: 10px;
            border-radius: 5px;
        }

        .text-section p {
            word-break: break-all;
            overflow-wrap: break-word;
            font-size: 14px;
            padding: 0 40px;
            font-family: 'Courier New', monospace;
        }

        button {
            background-color: rgba(30, 143, 255, 0.3);
            color: #fff;
            border: none;
            padding: 5px 10px;
            margin-top: 10px;
            margin-bottom: 10px;
            cursor: pointer;
            border-radius: 5px;
            width: 100px;
            font-weight: bold;
            transition: background-color 0.3s ease, box-shadow 0.3s ease;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.4);
        }

        button:hover {
            background-color: rgba(0, 122, 204, 0.5);
            box-shadow: 0 0 15px rgba(0, 122, 204, 0.7);
        }

        .theme-button {
            position: absolute;
            top: 20px;
            right: 20px;
            background-color: rgba(0, 0, 0, 0.5);
            border: none;
            cursor: pointer;
            font-size: 24px;
            color: #fff;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            justify-content: center;
            align-items: center;
            transition: background-color 0.3s ease;
        }

        @keyframes rotate {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }

        .theme-button.rotate {
            animation: rotate 1s ease-in-out;
        }

        .theme-button:hover {
            background-color: rgba(0, 0, 0, 0.7);
        }

        .social-links {
            margin-top: 20px;
        }

        .social-links a {
            color: #f1f1f1;
            text-decoration: none;
            margin: 0 10px;
            font-size: 24px;
            transition: color 0.3s ease;
        }

        .social-links a:hover {
            color: #1e90ff;
        }

        @media (max-width: 600px) {
            .container {
                width: 100%;
            }

            h1, h2 {
                font-size: 1.2em;
            }

            .text-section {
                padding: 10px;
            }

            button {
                padding: 8px 16px;
                width: 100%;
            }

            .theme-button {
                top: 10px;
                right: 10px;
                width: 30px;
                height: 30px;
                font-size: 20px;
            }
        }
    </style>
</head>
<body>
    <h1>GEO-PROJECT</h1>
    <div class="container">
        <div class="info">
            <h3 style="text-align: center;">IP INFO</h3>
            <p class="pinfo" id="pinfo">
                » Domain      : ${hostName}<br>
                » IP          : ${ip}<br>
                » ISP         : ${isp}<br>
                » Country     : ${country}<br>
                » City        : ${city}<br>
                » User ID     : ${userID}<br>
                » Port TLS    : 443<br>
                » Port NTLS   : 80<br>
                » Security    : auto<br>
                » Network     : (WS)<br>
                » Path        : /vless<br>
                » Path        : ${proxyip}<br>
            </p>
        </div>

        <div class="text-section">
            <h3>TLS - 443</h3>
            <p class="main" id="default-ip">${vlessTlsFormatted}</p>
            <button onclick="copyToClipboard('default-ip')">Copy Port 443</button>
        </div>

        <div class="text-section">
            <h3>NTLS - 80</h3>
            <p class="main" id="best-ip">${vlessNtlsFormatted}</p>
            <button onclick="copyToClipboard('best-ip')">Copy Port 80</button>
        </div>

        <div class="social-links">
            <a href="https://www.facebook.com" target="_blank" title="Facebook"><i class="fab fa-facebook-f"></i></a>
            <a href="https://wa.me/6282339191527" target="_blank" title="WhatsApp"><i class="fab fa-whatsapp"></i></a>
            <a href="https://github.com/jaka1m" target="_blank" title="GitHub"><i class="fab fa-github"></i></a>
            <a href="https://t.me/sampiiiiu" target="_blank" title="Telegram"><i class="fab fa-telegram-plane"></i></a>
        </div>
    </div>
    <button id="switch" class="theme-button">
        <i id="theme-icon" class="fas fa-sun"></i>
    </button>
    <script>
        function copyToClipboard(id) {
            const text = document.getElementById(id).innerText;
            navigator.clipboard.writeText(text).then(function() {
                alert('Text copied to clipboard!');
            }, function(err) {
                console.error('Could not copy text: ', err);
            });
        }

        document.getElementById('switch').addEventListener('click', function() {
            document.body.classList.toggle('dark-theme');
            this.classList.toggle('rotate');
        });
    </script>
</body>
</html>





`;
  } catch (error) {
    console.error("Error generating VLESS config:", error);
    return `<p>Error generating VLESS config. Please try again later.</p>`;
  }
}
export {
  worker_default as default
};
//# sourceMappingURL=_worker.js.map
