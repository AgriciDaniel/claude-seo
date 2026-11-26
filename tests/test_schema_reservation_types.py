"""Reservation subtypes use the time fields and reserved objects in Schema.org.

See https://schema.org/Reservation and each subtype's examples. The API's
generic start/end parameters must not produce restaurant fields for every kind.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import schema_generate  # noqa: E402

START = "2026-12-03T18:30:00+01:00"
END = "2026-12-04T10:00:00+01:00"
CASES = [
    ("FoodEstablishmentReservation", "FoodEstablishment", "startTime", "endTime", False),
    ("LodgingReservation", "LodgingBusiness", "checkinTime", "checkoutTime", False),
    ("RentalCarReservation", "Car", "pickupTime", "dropoffTime", False),
    ("TaxiReservation", "TaxiService", "pickupTime", None, False),
    ("EventReservation", "Event", "startDate", "endDate", True),
    ("TrainReservation", "TrainTrip", "departureTime", "arrivalTime", True),
    ("FlightReservation", "Flight", "departureTime", "arrivalTime", True),
]


@pytest.mark.parametrize("kind,object_type,start_key,end_key,nested", CASES)
def test_subtype_start_fields(kind, object_type, start_key, end_key, nested):
    result = schema_generate.reservation("Provider", START, kind=kind)
    reserved = result["reservationFor"]
    assert result["@type"] == kind
    assert reserved["@type"] == object_type
    target = reserved if nested else result
    assert target[start_key] == START
    if kind != "FoodEstablishmentReservation":
        assert "startTime" not in result
    if nested:
        assert start_key not in result
    if end_key:
        assert end_key not in target


@pytest.mark.parametrize("kind,object_type,start_key,end_key,nested", [case for case in CASES if case[3]])
def test_subtype_end_fields_preserve_the_supplied_time(kind, object_type, start_key, end_key, nested):
    result = schema_generate.reservation("Provider", START, end=END, kind=kind)
    target = result["reservationFor"] if nested else result
    assert target[start_key] == START
    assert target[end_key] == END
    if kind != "FoodEstablishmentReservation":
        assert "endTime" not in result
    if nested:
        assert end_key not in result


@pytest.mark.parametrize("kind", [case[0] for case in CASES])
def test_subtype_keeps_booking_and_customer_details(kind):
    result = schema_generate.reservation(
        "Provider", START, kind=kind, reservation_for_name="Reserved thing",
        reservation_id="booking-123", customer_name="Alex", customer_email="alex@example.com",
    )
    assert result["provider"] == {"@type": "Organization", "name": "Provider"}
    assert result["reservationFor"]["name"] == "Reserved thing"
    assert result["reservationId"] == "booking-123"
    assert result["underName"] == {"@type": "Person", "name": "Alex", "email": "alex@example.com"}
    assert result["reservationStatus"] == "https://schema.org/ReservationConfirmed"


@pytest.mark.parametrize("kind", ["FoodEstablishmentReservation", "TaxiReservation"])
def test_party_size_on_supported_reservation_types(kind):
    result = schema_generate.reservation("Provider", START, kind=kind, party_size=4)
    assert result["partySize"] == 4


@pytest.mark.parametrize("kind", [case[0] for case in CASES if case[0] not in {"FoodEstablishmentReservation", "TaxiReservation"}])
def test_party_size_is_not_emitted_for_unrelated_subtypes(kind):
    with pytest.raises(ValueError, match="party-size"):
        schema_generate.reservation("Provider", START, kind=kind, party_size=4)


def test_taxi_end_time_is_not_silently_discarded_or_mislabelled():
    with pytest.raises(ValueError, match="end"):
        schema_generate.reservation("Provider", START, end=END, kind="TaxiReservation")


def test_unknown_subtype_is_not_emitted_as_a_place():
    with pytest.raises(ValueError, match="Unsupported reservation kind"):
        schema_generate.reservation("Provider", START, kind="MadeUpReservation")


@pytest.mark.parametrize("kind,object_type,start_key,end_key,nested", CASES)
def test_each_cli_subtype_emits_its_own_time_fields(kind, object_type, start_key, end_key, nested):
    args = [
        sys.executable, str(SCRIPTS / "schema_generate.py"), "reservation",
        "--provider", "Provider", "--start", START, "--reservation-kind", kind,
    ]
    if end_key:
        args.extend(["--end", END])
    completed = subprocess.run(args, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    target = result["reservationFor"] if nested else result
    assert result["reservationFor"]["@type"] == object_type
    assert target[start_key] == START
    if end_key:
        assert target[end_key] == END


@pytest.mark.parametrize("args", [
    ["--reservation-kind", "TaxiReservation", "--end", END],
    ["--reservation-kind", "LodgingReservation", "--party-size", "4"],
])
def test_cli_invalid_subtype_options_are_usage_errors(args):
    completed = subprocess.run(
        [sys.executable, str(SCRIPTS / "schema_generate.py"), "reservation",
         "--provider", "Provider", "--start", START, *args],
        capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "error:" in completed.stderr
    assert "Traceback" not in completed.stderr
