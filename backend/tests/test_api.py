"""The web API, called the way the website will call it."""

from tests.conftest import clinic_time, clinic_time_iso, next_monday, utc_iso

API = "/api/v1"
ALI_PHONE = "07700 900123"


def booking(day, hour=13, minute=0, **changes):
    body = {
        "service_slug": "teeth-whitening",
        "dentist_slug": "omar-haddad",
        "start_time": clinic_time_iso(day, hour, minute),
        "full_name": "Ali Guest",
        "phone": ALI_PHONE,
    }
    return body | changes


async def register(client, email="ali@example.com"):
    r = await client.post(f"{API}/auth/register",
                          json={"email": email, "password": "correcthorse", "full_name": "Ali"})
    assert r.status_code == 201
    return r.json()


def bearer(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# --- Clinic -------------------------------------------------------------------------


async def test_clinic_content(client):
    assert len((await client.get(f"{API}/services")).json()) == 6
    assert len((await client.get(f"{API}/dentists")).json()) == 3
    assert len((await client.get(f"{API}/faqs")).json()) == 14
    assert (await client.get(f"{API}/services/teeth-whitening")).json()["duration_minutes"] == 60
    assert (await client.get(f"{API}/services/nope")).status_code == 404


# --- Auth ---------------------------------------------------------------------------


async def test_register_login_refresh_logout(client):
    tokens = await register(client, email="Ali@Example.com")

    me = await client.get(f"{API}/auth/me", headers=bearer(tokens))
    assert me.json()["email"] == "ali@example.com"  # stored lowercased
    assert (await client.get(f"{API}/auth/me")).status_code == 401

    login = await client.post(f"{API}/auth/login",
                              json={"email": "ALI@EXAMPLE.COM", "password": "correcthorse"})
    assert login.status_code == 200
    refresh_token = login.json()["refresh_token"]

    refreshed = await client.post(f"{API}/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200

    out = await client.post(f"{API}/auth/logout", json={"refresh_token": refresh_token})
    assert out.status_code == 204

    # The point of storing refresh tokens: after logout, the token is dead.
    dead = await client.post(f"{API}/auth/refresh", json={"refresh_token": refresh_token})
    assert dead.status_code == 401


async def test_auth_refusals(client):
    await register(client)
    again = await client.post(f"{API}/auth/register",
                              json={"email": "ALI@example.com", "password": "another-pass", "full_name": "X"})
    assert again.status_code == 409

    wrong = await client.post(f"{API}/auth/login", json={"email": "ali@example.com", "password": "nope-nope"})
    assert wrong.status_code == 401

    short = await client.post(f"{API}/auth/register",
                              json={"email": "new@example.com", "password": "short", "full_name": "X"})
    assert short.status_code == 422

    too_long = await client.post(f"{API}/auth/register",
                                 json={"email": "new@example.com", "password": "é" * 40, "full_name": "X"})
    assert too_long.status_code == 422  # 40 characters but 80 bytes - over bcrypt's limit


# --- Scheduling ---------------------------------------------------------------------


async def test_availability(client):
    day = next_monday()
    r = await client.get(f"{API}/availability", params={
        "service_slug": "teeth-whitening", "first_day": day.isoformat(), "dentist_slug": "omar-haddad"})
    assert r.status_code == 200
    free = r.json()
    assert len(free) == 15
    assert free[0] == {
        "dentist_slug": "omar-haddad",
        "start_time": utc_iso(clinic_time(day, 9, 0)),  # sent as UTC, ending in Z
        "end_time": utc_iso(clinic_time(day, 10, 0)),
    }


async def test_availability_refusals(client):
    day = next_monday().isoformat()
    unknown = await client.get(f"{API}/availability", params={"service_slug": "nope", "first_day": day})
    assert unknown.status_code == 404


async def test_guest_books_moves_and_cancels(client):
    day = next_monday()
    r = await client.post(f"{API}/appointments", json=booking(day))
    assert r.status_code == 201
    appt = r.json()
    assert appt["start_time"] == utc_iso(clinic_time(day, 13, 0))
    assert appt["dentist_name"] == "Dr Omar Haddad"

    mine = await client.post(f"{API}/appointments/mine", json={"phone": "07700-900123"})
    assert [a["id"] for a in mine.json()] == [appt["id"]]

    moved = await client.post(f"{API}/appointments/{appt['id']}/reschedule",
                              json={"phone": ALI_PHONE, "new_start_time": clinic_time_iso(day, 15, 0)})
    assert moved.status_code == 200
    assert moved.json()["start_time"] == utc_iso(clinic_time(day, 15, 0))

    cancelled = await client.post(f"{API}/appointments/{appt['id']}/cancel", json={"phone": ALI_PHONE})
    assert cancelled.json()["status"] == "cancelled"

    twice = await client.post(f"{API}/appointments/{appt['id']}/cancel", json={"phone": ALI_PHONE})
    assert twice.status_code == 400


async def test_booking_refusals(client):
    day = next_monday()
    assert (await client.post(f"{API}/appointments", json=booking(day))).status_code == 201

    taken = await client.post(f"{API}/appointments", json=booking(day, phone="07700 900456"))
    assert taken.status_code == 409

    no_timezone = await client.post(f"{API}/appointments",
                                    json=booking(day, start_time=f"{day.isoformat()}T10:00:00"))
    assert no_timezone.status_code == 422

    odd_time = await client.post(f"{API}/appointments", json=booking(day, 10, 17))
    assert odd_time.status_code == 400

    no_phone = await client.post(f"{API}/appointments/mine", json={})
    assert no_phone.status_code == 400


async def test_wrong_phone_cannot_cancel(client):
    appt = (await client.post(f"{API}/appointments", json=booking(next_monday()))).json()
    r = await client.post(f"{API}/appointments/{appt['id']}/cancel", json={"phone": "07700 900456"})
    assert r.status_code == 404


async def test_logged_in_booking_is_private_to_the_account(client):
    """Also guards the bug where logged-in bookings failed with a transaction error."""
    tokens = await register(client)
    day = next_monday()

    r = await client.post(f"{API}/appointments", json=booking(day), headers=bearer(tokens))
    assert r.status_code == 201
    appt = r.json()

    mine = await client.post(f"{API}/appointments/mine", json={}, headers=bearer(tokens))
    assert [a["id"] for a in mine.json()] == [appt["id"]]

    # A guest who types the same phone number sees nothing and can cancel nothing.
    guest = await client.post(f"{API}/appointments/mine", json={"phone": ALI_PHONE})
    assert guest.json() == []
    stranger = await client.post(f"{API}/appointments/{appt['id']}/cancel", json={"phone": ALI_PHONE})
    assert stranger.status_code == 404

    own = await client.post(f"{API}/appointments/{appt['id']}/cancel", json={}, headers=bearer(tokens))
    assert own.json()["status"] == "cancelled"
