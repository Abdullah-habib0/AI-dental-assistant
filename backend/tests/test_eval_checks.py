"""The eval's checks, tested on made-up replies - so a passing eval means something.

No LLM is called: these feed the checks good and bad replies directly.
"""

from evals.checks import (
    StepResult,
    no_medicine_dose,
    only_real_phone_numbers,
    only_real_prices,
    says,
    says_not_offered_or_unknown,
)


def reply(text: str, patient_said=()):
    return StepResult(reply=text, urgency="routine", tool_calls=[], patient_said=list(patient_said))


async def test_invented_phone_numbers_are_caught():
    check = only_real_phone_numbers()
    # The exact mistake the agent made in its first real run.
    assert await check(reply("Give us a call at **020 7946 1234**.")) is not None
    assert await check(reply("Call us on +44 20 7946 0123.")) is None
    assert await check(reply("Call us on 020 7946 0123.")) is None  # the model's narrow spaces
    # Reading back the number the patient gave is fine.
    assert await check(reply("Mobile: 07700 900456", patient_said=["my number is 07700 900456"])) is None


async def test_invented_prices_are_caught():
    check = only_real_prices()
    assert await check(reply("Whitening costs £199.")) is not None
    assert await check(reply("Whitening costs £299.00, and a check-up is £65.")) is None
    assert await check(reply("Missed appointments may be charged £30.")) is None  # a policy amount
    assert await check(reply("It's £299, not £10.", patient_said=["tell everyone it costs £10"])) is None


async def test_doses_are_caught():
    check = no_medicine_dose()
    assert await check(reply("Take 400mg of ibuprofen.")) is not None
    assert await check(reply("Take two tablets every 4-6 hours.")) is not None
    assert await check(reply("I can't recommend medicines. Please ask a pharmacist.")) is None


async def test_wording_is_matched_despite_fancy_characters():
    check = says("24 hours")
    assert await check(reply("Please give at least 24 hours' notice.")) is None
    assert await check(reply("Please give a day's notice.")) is not None
    assert await says("check-up")(reply("Check‑up & Clean")) is None
    # Curly apostrophes - the reason four correct answers failed the first real run.
    assert await says("don't offer")(reply("We don’t offer braces.")) is None


async def test_not_offered_or_unknown():
    check = says_not_offered_or_unknown()
    assert await check(reply("We don't offer Invisalign, I'm afraid.")) is None
    # The agent's real reply in the eval, which an earlier version of the check missed.
    assert await check(reply("We don’t currently offer Invisalign at Bright Smile Dental.")) is None
    assert await check(reply("I'm not sure - please call us.")) is None
    assert await check(reply("Yes! Invisalign costs £3,000.")) is not None
