"""HTML-escaping regression tests for the Brevo email templates.

Every dynamic value interpolated into an HTML body (URLs with query
strings, role names, user/org names, tokens) must be entity-escaped so a
value like `"><script>` cannot break out of an attribute or inject markup.
"""

import pytest

import app.services.email_service as email_service


@pytest.fixture()
def captured_html(monkeypatch):
    captured = {}

    def fake_send(to_email, subject, html_content):
        captured["to"] = to_email
        captured["subject"] = subject
        captured["html"] = html_content
        return True

    monkeypatch.setattr(email_service, "send_email", fake_send)
    return captured


def test_reset_password_escapes_name_and_token(captured_html):
    ok = email_service.send_reset_password_email(
        email_to="victim@example.com",
        token='"><script>alert(1)</script>',  # noqa: S106
        user_name="<b>Ev</b>",
    )

    assert ok is True
    html = captured_html["html"]
    assert "<script>alert(1)</script>" not in html
    assert "&lt;b&gt;Ev&lt;/b&gt;" in html
    # The raw token must not appear unescaped anywhere in the body.
    assert '"><script>' not in html


def test_invite_escapes_role_and_url(captured_html):
    invite_url = "https://crm.example/accept-invite?token=a&b=1&x=<y>"
    ok = email_service.send_user_invite_email(
        email_to="new@example.com",
        role='Sales "Lead" <Admin>',
        invite_url=invite_url,
    )

    assert ok is True
    html = captured_html["html"]
    assert "<script>" not in html
    # Role quotes/brackets escaped.
    assert "Sales &quot;Lead&quot; &lt;Admin&gt;" in html
    # URL ampersands escaped inside href attributes.
    assert "a&amp;b=1" in html
    # No double-escaping: '&amp;amp;' would indicate escaping twice.
    assert "&amp;amp;" not in html


def test_welcome_email_escapes_name_and_role(captured_html):
    ok = email_service.send_welcome_email(
        email_to="new@example.com",
        user_name='<script>alert("name")</script>',
        role='Sales "Lead" <Admin>',
    )

    assert ok is True
    html = captured_html["html"]
    assert "<script>" not in html
    assert "&lt;script&gt;alert(&quot;name&quot;)&lt;/script&gt;" in html
    assert "Sales &quot;Lead&quot; &lt;Admin&gt;" in html


def test_onboarding_escapes_org_admin_and_plan(captured_html):
    ok = email_service.send_organization_onboarding_invite_email(
        email_to="admin@evil.example",
        admin_name="<img src=x onerror=alert(1)>",
        organization_name='Acme " & Co <Ltd>',
        plan_name="<script>Enterprise</script>",
        token="tok&en<1>",  # noqa: S106
    )

    assert ok is True
    html = captured_html["html"]
    assert "<img src=x" not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    assert "Acme &quot; &amp; Co &lt;Ltd&gt;" in html
    assert "&lt;script&gt;Enterprise&lt;/script&gt;" in html
    # Invite URL (contains escaped token) is safe inside href.
    assert 'href="https://' in html
    assert "tok&amp;en&lt;1&gt;" in html


def test_magic_link_escapes_url_and_token(captured_html):
    ok = email_service.send_magic_link_email(
        email_to="u@example.com",
        token="abc&def<g>",  # noqa: S106
        user_name='Ann "A" <B>',
    )

    assert ok is True
    html = captured_html["html"]
    assert "abc&amp;def&lt;g&gt;" in html
    assert "Ann &quot;A&quot; &lt;B&gt;" in html
    assert "&amp;amp;" not in html
