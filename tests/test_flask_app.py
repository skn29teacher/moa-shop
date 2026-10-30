def test_flask_serves_frontend_and_static_assets(client):
    home = client.get("/")
    assert home.status_code == 200
    assert b"moa" in home.data

    stylesheet = client.get("/static/css/app.css")
    assert stylesheet.status_code == 200
    assert stylesheet.mimetype == "text/css"
