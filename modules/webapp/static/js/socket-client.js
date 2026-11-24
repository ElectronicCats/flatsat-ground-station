/*
 * Minimal Socket.IO / Engine.IO v4 client — vanilla JS, no CDN, no build.
 *
 * The dashboard used to load socket.io from cdnjs.cloudflare.com, which
 * silently breaks the live telemetry feed on any machine without internet
 * access (labs, conference rooms, CTF environments).  This client speaks
 * just enough of the protocol to replace it:
 *
 *   Engine.IO v4 packets (websocket transport)
 *     0{...}  open      -> send "40" to join the default namespace
 *     2       ping      -> reply "3" (pong)
 *     3       pong
 *     4...    message   -> Socket.IO packet
 *     1       close
 *
 *   Socket.IO packets
 *     0{...}  CONNECT      -> "connect" event
 *     2[...]  EVENT        -> dispatch payload[0] as the event name
 *     4{...}  CONNECT_ERROR
 *
 * Public API (subset of the socket.io client used by the dashboard):
 *   socket.on(event, handler)   socket.connect()   socket.connected
 */
(function (global) {
    "use strict";

    function SocketClient(options) {
        options = options || {};
        this.path = options.path || "/socket.io/";
        this.handlers = {};
        this.ws = null;
        this.connected = false;
        this.retryDelay = options.retryDelay || 3000;
        this._retryTimer = null;
        this._shouldRun = true;
    }

    SocketClient.prototype.on = function (event, handler) {
        if (!this.handlers[event]) {
            this.handlers[event] = [];
        }
        this.handlers[event].push(handler);
        return this;
    };

    SocketClient.prototype.fire = function (event, payload) {
        var list = this.handlers[event] || [];
        for (var i = 0; i < list.length; i++) {
            try {
                list[i](payload);
            } catch (err) {
                console.error("[socket] error in handler for '" + event + "':", err);
            }
        }
    };

    SocketClient.prototype.connect = function () {
        var self = this;
        if (this.ws && (this.ws.readyState === 0 || this.ws.readyState === 1)) {
            return this;
        }

        var proto = global.location.protocol === "https:" ? "wss:" : "ws:";
        var url =
            proto +
            "//" +
            global.location.host +
            this.path +
            "?EIO=4&transport=websocket";

        try {
            this.ws = new global.WebSocket(url);
        } catch (err) {
            console.error("[socket] cannot open WebSocket:", err);
            this._scheduleRetry();
            return this;
        }

        this.ws.onmessage = function (evt) {
            self._onMessage(evt.data);
        };
        this.ws.onclose = function () {
            var wasConnected = self.connected;
            self.connected = false;
            if (wasConnected) {
                self.fire("disconnect");
            }
            self._scheduleRetry();
        };
        this.ws.onerror = function () {
            // onclose always follows, which handles the retry.
        };

        return this;
    };

    SocketClient.prototype.disconnect = function () {
        this._shouldRun = false;
        if (this._retryTimer) {
            global.clearTimeout(this._retryTimer);
            this._retryTimer = null;
        }
        if (this.ws) {
            try {
                this.ws.close();
            } catch (e) {
                /* ignore */
            }
        }
        this.connected = false;
    };

    SocketClient.prototype._scheduleRetry = function () {
        var self = this;
        if (!this._shouldRun || this._retryTimer) {
            return;
        }
        this._retryTimer = global.setTimeout(function () {
            self._retryTimer = null;
            self.connect();
        }, this.retryDelay);
    };

    SocketClient.prototype._onMessage = function (raw) {
        if (typeof raw !== "string" || !raw.length) {
            return;
        }

        var type = raw.charAt(0);
        var body = raw.slice(1);

        if (type === "0") {
            // Engine.IO open -> join the default namespace.
            this._send("40");
            return;
        }
        if (type === "2") {
            this._send("3"); // ping -> pong
            return;
        }
        if (type === "1") {
            // Engine.IO close
            if (this.ws) {
                try {
                    this.ws.close();
                } catch (e) {
                    /* ignore */
                }
            }
            return;
        }
        if (type !== "4") {
            return;
        }

        // Socket.IO packet
        var sioType = body.charAt(0);
        var rest = body.slice(1);

        // Strip the namespace prefix ("/admin,...") when present.
        if (rest.charAt(0) !== "[" && rest.charAt(0) !== "{") {
            var comma = rest.indexOf(",");
            if (comma > 0) {
                rest = rest.slice(comma + 1);
            }
        }

        if (sioType === "0") {
            // CONNECT
            this.connected = true;
            this.fire("connect", this._parse(rest));
        } else if (sioType === "2") {
            // EVENT
            var payload = this._parse(rest);
            if (payload && payload.length) {
                this.fire(payload[0], payload.length > 1 ? payload[1] : null);
            }
        } else if (sioType === "4") {
            this.fire("connect_error", this._parse(rest));
        }
    };

    SocketClient.prototype._parse = function (text) {
        try {
            return JSON.parse(text);
        } catch (err) {
            return null;
        }
    };

    SocketClient.prototype._send = function (data) {
        if (this.ws && this.ws.readyState === 1) {
            try {
                this.ws.send(data);
            } catch (err) {
                /* ignore */
            }
        }
    };

    global.FlatSatSocket = SocketClient;
    global.socket = new SocketClient();
})(window);
