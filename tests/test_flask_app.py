def test_flask_serves_frontend_and_static_assets(client):
    home = client.get("/")
    assert home.status_code == 200
    assert b"moa" in home.data

    stylesheet = client.get("/static/css/app.css")
    assert stylesheet.status_code == 200
    assert stylesheet.mimetype == "text/css"


def test_email_confirmation_callback_serves_login_bootstrap_without_creating_session(client):
    response = client.get('/auth/confirm')
    assert response.status_code == 200
    assert b'/static/js/auth-confirmation.js' in response.data
    assert 'no-store' in response.headers['Cache-Control']
    assert 'set-cookie' not in response.headers
    assert client.get('/api/members/me').status_code == 401
