"""Fills the database with the clinic's demo data.

Safe to run as many times as you like: it clears these tables first, so you never end
up with two copies of the same service.

Run it from the backend folder with:   python -m scripts.seed
"""

import asyncio

from sqlalchemy import delete

from app.db.init_db import create_tables
from app.db.session import SessionLocal, engine
from app.features.clinic.models import Dentist, Faq, Service

SERVICES = [
    Service(
        slug="check-up-and-clean",
        name="Check-up & Clean",
        summary="A full examination and professional scale and polish.",
        description=(
            "Your dentist checks your teeth, gums and soft tissues, then a hygienist "
            "removes plaque and tartar and polishes the surfaces. We recommend this "
            "every six months for most patients."
        ),
        duration_minutes=30,
        price_cents=6500,
    ),
    Service(
        slug="teeth-whitening",
        name="Teeth Whitening",
        summary="Professional whitening, several shades lighter in one visit.",
        description=(
            "A protective barrier is placed over your gums and a whitening gel is "
            "applied to the teeth. Results vary between patients, and whitening does "
            "not change the colour of crowns, veneers or fillings."
        ),
        duration_minutes=60,
        price_cents=29900,
    ),
    Service(
        slug="dental-filling",
        name="Dental Filling",
        summary="Tooth-coloured filling to repair decay or a small fracture.",
        description=(
            "The damaged part of the tooth is removed and replaced with a composite "
            "filling matched to the shade of your tooth. Usually done under local "
            "anaesthetic in a single visit."
        ),
        duration_minutes=30,
        price_cents=12000,
    ),
    Service(
        slug="root-canal",
        name="Root Canal Treatment",
        summary="Treatment to save a tooth with an infected nerve.",
        description=(
            "The infected pulp is removed, the canals are cleaned and shaped, and the "
            "space is sealed. A crown is often recommended afterwards to protect the "
            "tooth. Carried out under local anaesthetic."
        ),
        duration_minutes=90,
        price_cents=45000,
    ),
    Service(
        slug="dental-implant",
        name="Dental Implant",
        summary="A permanent replacement for a missing tooth.",
        description=(
            "A titanium post is placed into the jawbone and left to heal, after which "
            "a crown is fitted on top. Treatment runs over several months and begins "
            "with a consultation and a scan."
        ),
        duration_minutes=90,
        price_cents=185000,
    ),
    Service(
        slug="tooth-extraction",
        name="Tooth Extraction",
        summary="Removal of a tooth that cannot be saved.",
        description=(
            "Carried out under local anaesthetic. We will always discuss the "
            "alternatives with you first, and talk through replacement options and "
            "aftercare before you leave."
        ),
        duration_minutes=30,
        price_cents=15000,
    ),
]

DENTISTS = [
    Dentist(
        slug="sarah-whitfield",
        name="Dr Sarah Whitfield",
        qualifications="BDS, MJDF RCS",
        speciality="General & Cosmetic Dentistry",
        bio=(
            "Sarah has led the practice since 2014 and looks after most of our family "
            "patients. She has a particular interest in cosmetic work and in treating "
            "nervous patients gently."
        ),
        photo_url="/images/team/sarah-whitfield.jpg",
    ),
    Dentist(
        slug="omar-haddad",
        name="Dr Omar Haddad",
        qualifications="BDS, MSc Endodontics",
        speciality="Endodontics (Root Canal Treatment)",
        bio=(
            "Omar handles our more complex root canal cases and takes referrals from "
            "practices across the city. He teaches part-time on the postgraduate "
            "endodontics programme."
        ),
        photo_url="/images/team/omar-haddad.jpg",
    ),
    Dentist(
        slug="mei-tanaka",
        name="Dr Mei Tanaka",
        qualifications="BDS, MSc Oral Surgery",
        speciality="Implants & Oral Surgery",
        bio=(
            "Mei places all of our implants and carries out surgical extractions. She "
            "has been placing implants for over a decade and plans every case from a "
            "3D scan."
        ),
        photo_url="/images/team/mei-tanaka.jpg",
    ),
]

FAQS = [
    Faq(
        category="Appointments",
        question="How do I book an appointment?",
        answer=(
            "Use the chat on this website and our assistant will find you a time, or "
            "call the practice during opening hours."
        ),
    ),
    Faq(
        category="Appointments",
        question="What are your opening hours?",
        answer="We are open Monday to Friday, 9am to 5pm. We are closed at weekends.",
    ),
    Faq(
        category="Appointments",
        question="Can I choose which dentist I see?",
        answer=(
            "Yes. You can ask for a particular dentist when you book, or leave it to us "
            "and we will give you the earliest available appointment."
        ),
    ),
    Faq(
        category="Appointments",
        question="What if I need to cancel or move my appointment?",
        answer=(
            "Let us know at least 24 hours beforehand and there is no charge. You can "
            "do this through the chat, or by calling us."
        ),
    ),
    Faq(
        category="Appointments",
        question="What happens if I miss my appointment?",
        answer=(
            "A missed appointment without notice may be charged at 30 pounds. We will "
            "always contact you first to check everything is alright."
        ),
    ),
    Faq(
        category="Payment",
        question="How much does treatment cost?",
        # No amounts here on purpose: prices live in the services table only, so changing
        # a price can never leave an old figure behind in an FAQ.
        answer=(
            "Every treatment's current price is shown on our services page, and the chat "
            "assistant can tell you the price of any treatment."
        ),
    ),
    Faq(
        category="Payment",
        question="Which payment methods do you accept?",
        answer="Card, cash and bank transfer. Payment is taken on the day of treatment.",
    ),
    Faq(
        category="Payment",
        question="Do you offer payment plans?",
        answer=(
            "Yes. For treatment over 500 pounds we can spread the cost over several "
            "months. Ask at reception and we will talk you through the options."
        ),
    ),
    Faq(
        category="Treatments",
        question="Does a filling hurt?",
        answer=(
            "The area is numbed with a local anaesthetic first, so you should not feel "
            "pain during the treatment. Tell your dentist at any point if you are "
            "uncomfortable."
        ),
    ),
    Faq(
        category="Treatments",
        question="How long does whitening last?",
        answer=(
            "Usually between one and three years. It lasts longer if you avoid smoking "
            "and go easy on coffee, tea and red wine."
        ),
    ),
    Faq(
        category="Treatments",
        question="How often should I have a check-up?",
        answer=(
            "Every six months suits most people. Your dentist may suggest coming more "
            "often if you are being treated for gum disease."
        ),
    ),
    Faq(
        category="The Practice",
        question="Where are you and is there parking?",
        answer=(
            "We are at 12 High Street, a five minute walk from the station. There is "
            "paid street parking directly outside and a car park behind the library."
        ),
    ),
    Faq(
        category="The Practice",
        question="Is the practice accessible?",
        answer=(
            "Yes. There is step-free access from the street and a ground floor surgery. "
            "Please mention any access needs when you book so we can plan ahead."
        ),
    ),
    Faq(
        category="The Practice",
        question="Do you treat children?",
        answer=(
            "Yes, we see patients of all ages. First visits for children are short and "
            "relaxed, so they get used to the practice before any treatment is needed."
        ),
    ),
]


async def seed() -> None:
    await create_tables(engine)

    async with SessionLocal() as session:
        async with session.begin():
            # Clear first, so running this twice does not create duplicates.
            await session.execute(delete(Faq))
            await session.execute(delete(Dentist))
            await session.execute(delete(Service))

            session.add_all(SERVICES)
            session.add_all(DENTISTS)
            session.add_all(FAQS)

    print(f"Seeded {len(SERVICES)} services, {len(DENTISTS)} dentists, {len(FAQS)} FAQs.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
