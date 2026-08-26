from flask import Flask, jsonify, redirect, request

from app.services.affiliate_link_service import build_affiliate_link, get_link_stats, load_affiliate_config, record_click


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/affiliate/programs")
    def programs():
        return jsonify({"programs": load_affiliate_config().get("programs", [])})

    @app.post("/affiliate/wrap")
    def wrap():
        data = request.get_json(silent=True) or {}
        if not data.get("url"):
            return jsonify({"detail": "url is required"}), 422

        result = build_affiliate_link(
            data["url"],
            base_url=(data.get("public_base_url") or request.host_url).rstrip("/"),
            use_redirect_tracking=data.get("use_redirect_tracking", True),
            shorten=data.get("shorten", True),
            sub_id=data.get("sub_id"),
            campaign=data.get("campaign"),
        )
        return jsonify(result)

    @app.get("/r/<code>")
    @app.get("/affiliate/r/<code>")
    @app.get("/go/<code>")
    def redirect_short_link(code: str):
        link = record_click(
            code,
            user_agent=request.headers.get("user-agent"),
            referer=request.headers.get("referer"),
            ip=request.remote_addr,
        )
        if not link:
            return jsonify({"detail": "Short affiliate link not found."}), 404
        return redirect(link["affiliate_url"], code=302)

    @app.get("/affiliate/stats/<code>")
    def stats(code: str):
        result = get_link_stats(code)
        if not result:
            return jsonify({"detail": "Short affiliate link not found."}), 404
        return jsonify(result)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
