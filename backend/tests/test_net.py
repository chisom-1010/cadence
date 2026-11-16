from app import net


def test_clean_domain():
    assert net.clean_domain("https://www.Acme.com/about?x=1") == "acme.com"
    assert net.clean_domain("acme.co.uk") == "acme.co.uk"
    assert net.clean_domain("user@acme.com") == "acme.com"
    for bad in ["", None, "not a domain", "localhost", "http://", "-bad-.com", "a..com"]:
        assert net.clean_domain(bad) is None


def test_private_and_internal_hosts_are_blocked():
    for host in ["127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254", "localhost", "0.0.0.0"]:
        assert net.is_public_host(host) is False, host


def test_host_with_any_private_address_is_blocked(monkeypatch):
    def gai(host, port):
        return [(2, 1, 6, "", ("93.184.216.34", 0)), (2, 1, 6, "", ("10.0.0.8", 0))]
    monkeypatch.setattr(net.socket, "getaddrinfo", gai)
    assert net.is_public_host("rebind.example.com") is False
    monkeypatch.setattr(net.socket, "getaddrinfo", lambda h, p: [(2, 1, 6, "", ("93.184.216.34", 0))])
    assert net.is_public_host("example.com") is True


def test_fetch_refuses_private_targets_and_odd_ports(monkeypatch):
    called = []
    monkeypatch.setattr(net.httpx, "stream", lambda *a, **k: called.append(1))
    assert net.fetch_html("http://127.0.0.1/admin") is None
    assert net.fetch_html("http://169.254.169.254/latest/meta-data") is None
    assert net.fetch_html("file:///etc/passwd") is None
    monkeypatch.setattr(net.socket, "getaddrinfo", lambda h, p: [(2, 1, 6, "", ("93.184.216.34", 0))])
    assert net.fetch_html("http://example.com:8080/") is None
    assert called == []  # no request was ever made


def test_html_to_text_keeps_title_and_description_and_drops_noise():
    html = """<html><head><title>Acme Freight</title><meta name="description" content="Road freight."></head>
    <body><nav>MENU LINKS</nav><script>var secret=1;</script><h1>We move pallets</h1><p>Across   the region.</p>
    <footer>Copyright</footer></body></html>"""
    text = net.html_to_text(html, 1000)
    assert "Title: Acme Freight" in text and "Description: Road freight." in text
    assert "We move pallets Across the region." in text
    assert "MENU" not in text and "secret" not in text and "Copyright" not in text
    assert len(net.html_to_text(html * 50, 100)) <= 100
