// Force Unlighthouse 0.13.5's Axios requests through the Python egress guard.
// Its CLI calls fetchUrlRaw before Puppeteer starts and the core sets
// axiosOptions.proxy = false, so HTTP_PROXY and HTTPS_PROXY are insufficient.
// The preload is inherited by npm but activates only in unlighthouse-ci.
if (process.argv.some(arg => /[\\/]unlighthouse-ci(?:\.cjs)?$/i.test(arg))) {
  const http = require('node:http');
  const https = require('node:https');
  const net = require('node:net');
  const tls = require('node:tls');
  const proxy = new URL(process.env.CLAUDE_SEO_GUARD_PROXY);
  const proxyPort = Number(proxy.port);
  const directHttpRequest = http.request;
  const directHttpsRequest = https.request;

  function requestTarget(input, options, protocol) {
    if (typeof input === 'string' || input instanceof URL)
      return new URL(input);
    const opts = { ...input, ...options };
    const host = opts.hostname || opts.host;
    const port = opts.port ? `:${opts.port}` : '';
    return new URL(`${protocol}//${host}${port}${opts.path || '/'}`);
  }

  function normalizeArgs(input, options, callback) {
    if (typeof options === 'function') return [input, {}, options];
    return [input, options || {}, callback];
  }

  function guardedHttp(input, options, callback) {
    [input, options, callback] = normalizeArgs(input, options, callback);
    const target = requestTarget(input, options, 'http:');
    const opts = typeof input === 'object' && !(input instanceof URL) ? { ...input, ...options } : { ...options };
    // Puppeteer itself uses a loopback WebSocket to control Chrome. Axios
    // sends ordinary GETs, so this narrow exception does not permit an
    // HTTP redirect to a local service.
    if ((target.hostname === '127.0.0.1' || target.hostname === '::1')
        && target.pathname.startsWith('/devtools/browser/')
        && String(opts.headers?.Upgrade || opts.headers?.upgrade).toLowerCase() === 'websocket')
      return directHttpRequest.call(http, {
        ...opts,
        hostname: target.hostname,
        port: target.port,
        path: `${target.pathname}${target.search}`,
      }, callback);
    delete opts.host;
    return directHttpRequest.call(http, {
      ...opts,
      protocol: 'http:',
      hostname: proxy.hostname,
      port: proxyPort,
      path: target.href,
      agent: false,
      headers: { ...opts.headers, Host: target.host },
    }, callback);
  }

  class GuardedHttpsAgent extends https.Agent {
    createConnection(options, callback) {
      const upstream = net.connect(proxyPort, proxy.hostname);
      const authority = `${options.host}:${options.port || 443}`;
      let pending = Buffer.alloc(0);
      upstream.once('connect', () => upstream.write(
        `CONNECT ${authority} HTTP/1.1\r\nHost: ${authority}\r\n\r\n`
      ));
      upstream.on('data', function onData(chunk) {
        pending = Buffer.concat([pending, chunk]);
        const end = pending.indexOf('\r\n\r\n');
        if (end < 0) {
          if (pending.length > 8192) upstream.destroy(new Error('Proxy response too large'));
          return;
        }
        upstream.removeListener('data', onData);
        if (!/^HTTP\/1\.[01] 200\b/.test(pending.subarray(0, end).toString('ascii'))) {
          upstream.destroy(new Error('Destination refused by egress guard'));
          return;
        }
        if (pending.length > end + 4) upstream.unshift(pending.subarray(end + 4));
        const secure = tls.connect({
          ...options,
          socket: upstream,
          servername: options.servername || options.host,
        });
        callback(null, secure);
      });
      upstream.once('error', callback);
    }
  }

  function guardedHttps(input, options, callback) {
    [input, options, callback] = normalizeArgs(input, options, callback);
    const target = requestTarget(input, options, 'https:');
    const opts = typeof input === 'object' && !(input instanceof URL) ? { ...input, ...options } : { ...options };
    delete opts.host;
    const previous = opts.agent && opts.agent.options ? opts.agent.options : {};
    return directHttpsRequest.call(https, {
      ...opts,
      protocol: 'https:',
      hostname: target.hostname,
      port: target.port || 443,
      path: `${target.pathname}${target.search}`,
      agent: new GuardedHttpsAgent(previous),
    }, callback);
  }

  http.request = guardedHttp;
  https.request = guardedHttps;
  http.get = (...args) => { const req = guardedHttp(...args); req.end(); return req; };
  https.get = (...args) => { const req = guardedHttps(...args); req.end(); return req; };
}
