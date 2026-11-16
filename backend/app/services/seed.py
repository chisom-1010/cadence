"""Fictional demo companies with website text already filled in, so the research step works
offline. They use the reserved .example domain, which can never resolve to a real site."""

SEED_LEADS = [
    {"company_name": "Brightline Freight (demo)", "domain": "brightline-freight.example", "contact_name": "Amara Okafor", "contact_role": "Head of Operations", "contact_email": "amara@brightline-freight.example",
     "website_text": "Title: Brightline Freight\nDescription: Regional road freight for growing retailers.\nBrightline Freight moves pallets and parcels across West Africa with a fleet of 60 trucks. Retailers book collections online, track every delivery in real time and get proof of delivery within the hour. We recently opened a cross-border hub in Lome to cut customs delays for clients shipping between Togo, Benin and Ghana. Our dispatch team still plans routes by hand in spreadsheets, and we are looking for ways to reduce empty return trips and late deliveries."},
    {"company_name": "Sunrise Dental Group (demo)", "domain": "sunrise-dental.example", "contact_name": "Dr. Kofi Mensah", "contact_role": "Practice Manager", "contact_email": "kofi@sunrise-dental.example",
     "website_text": "Title: Sunrise Dental Group\nDescription: Family dentistry in five city clinics.\nSunrise Dental Group runs five clinics with 22 dentists and hygienists. Patients book by phone or walk-in, and our front desks spend much of the day confirming appointments and chasing missed visits. This year we are adding a pediatric wing and extended evening hours. We value gentle care, short waiting times and clear pricing, and we are hiring two more receptionists to keep up with demand."},
    {"company_name": "Kente & Co Fashion (demo)", "domain": "kenteco-fashion.example", "contact_name": "Efua Boateng", "contact_role": "Founder", "contact_email": "efua@kenteco-fashion.example",
     "website_text": "Title: Kente & Co\nDescription: Handmade African prints, shipped worldwide.\nKente & Co is an online fashion store selling handmade clothing and accessories made by 40 artisans. We ship to over 30 countries and ship about 300 orders a month from our workshop. Our founder started the brand in 2021 and we just launched a men's line. Customer messages arrive on Instagram, WhatsApp and email, and a team of three answers all of them. Returns and sizing questions are our most common requests."},
    {"company_name": "Ledgerwise Accounting (demo)", "domain": "ledgerwise-accounting.example", "contact_name": "Samuel Adeyemi", "contact_role": "Managing Partner", "contact_email": "samuel@ledgerwise-accounting.example",
     "website_text": "Title: Ledgerwise Accounting\nDescription: Bookkeeping and tax for small businesses.\nLedgerwise is a 12-person accounting firm serving about 150 small businesses with monthly bookkeeping, payroll and annual tax filing. Clients send receipts by photo and email, and our staff key them into accounting software by hand. Busy season runs from January to April and we turn away new clients because the team is at capacity. We are exploring ways to automate document collection and reminders."},
    {"company_name": "Stonebridge Building Supplies (demo)", "domain": "stonebridge-supplies.example", "contact_name": "Grace Nkemelu", "contact_role": "Sales Director", "contact_email": "grace@stonebridge-supplies.example",
     "website_text": "Title: Stonebridge Building Supplies\nDescription: Cement, steel and tools for contractors.\nStonebridge distributes cement, roofing, steel bars and hand tools to contractors and small builders from three warehouses. Most orders are taken by phone and a sales team of eight quotes each job manually. Contractors often ask for quotes outside office hours and move on to a competitor if they wait. We recently added delivery to job sites and want to grow repeat business with mid-sized contractors."},
    {"company_name": "Pulse HR (demo)", "domain": "pulsehr.example", "contact_name": "Linda Mwangi", "contact_role": "Head of Growth", "contact_email": "linda@pulsehr.example",
     "website_text": "Title: Pulse HR\nDescription: Leave, attendance and payroll for African SMEs.\nPulse HR is a software company with 25 staff that sells leave tracking, attendance and payroll tools to small and medium businesses. Our sales team finds customers mostly through referrals and conferences, and we want a more predictable pipeline. We have 400 paying customers and recently launched mobile money payroll payouts. We are hiring two sales development reps this quarter."},
    {"company_name": "Mama Nkechi's Kitchen (demo)", "domain": "mamankechis.example", "contact_name": "Nkechi Eze", "contact_role": "Owner", "contact_email": "nkechi@mamankechis.example",
     "website_text": "Title: Mama Nkechi's Kitchen\nDescription: Home-style Nigerian food, six locations.\nMama Nkechi's Kitchen serves jollof rice, pepper soup and grilled fish at six restaurants and a catering service for weddings and offices. Orders come in through walk-ins, phone calls and two delivery apps. Our catering inquiries often sit unanswered for a day because the owner replies personally. We are planning a seventh location next year."},
    {"company_name": "Lingua Bridge Academy (demo)", "domain": "linguabridge.example", "contact_name": "Pierre Dossou", "contact_role": "Director", "contact_email": "pierre@linguabridge.example",
     "website_text": "Title: Lingua Bridge Academy\nDescription: French and English courses for professionals.\nLingua Bridge Academy teaches French and English to working professionals and university students, with evening classes and corporate training. We have 600 active students and 18 teachers across two campuses. Enrolment is handled by two administrators who answer inquiries by phone and email. We want to reach more companies that need language training for their staff."},
]


# People for the demo leads, so "Find people" works offline. Fictional, like the companies.
# Statuses are mixed on purpose so every email state can be shown in the demo.
SEED_PEOPLE = {
    "brightline-freight.example": [
        ("Amara Okafor", "Head of Operations", "amara@brightline-freight.example", "found"),
        ("Tunde Bakare", "Fleet Manager", "tunde.bakare@brightline-freight.example", "guessed"),
        ("Esi Quartey", "Chief Executive Officer", "esi.quartey@brightline-freight.example", "guessed"),
    ],
    "sunrise-dental.example": [
        ("Dr. Kofi Mensah", "Practice Manager", "kofi@sunrise-dental.example", "found"),
        ("Abena Owusu", "Lead Dentist", None, "no_mail_server"),
    ],
    "kenteco-fashion.example": [
        ("Efua Boateng", "Founder", "efua@kenteco-fashion.example", "found"),
        ("Kojo Asante", "Head of Customer Care", "kojo.asante@kenteco-fashion.example", "guessed"),
    ],
    "ledgerwise-accounting.example": [
        ("Samuel Adeyemi", "Managing Partner", "samuel@ledgerwise-accounting.example", "found"),
        ("Ngozi Eze", "Senior Accountant", "ngozi.eze@ledgerwise-accounting.example", "guessed"),
    ],
    "stonebridge-supplies.example": [
        ("Grace Nkemelu", "Sales Director", "grace@stonebridge-supplies.example", "found"),
        ("Emeka Obi", "Operations Manager", "emeka.obi@stonebridge-supplies.example", "guessed"),
        ("General inbox", "Company address", "sales@stonebridge-supplies.example", "role_address"),
    ],
    "pulsehr.example": [
        ("Linda Mwangi", "Head of Growth", "linda@pulsehr.example", "found"),
        ("Yaw Darko", "Chief Technology Officer", "yaw.darko@pulsehr.example", "guessed"),
    ],
    "mamankechis.example": [
        ("Nkechi Eze", "Owner", "nkechi@mamankechis.example", "found"),
        ("Chidi Eze", "Catering Manager", "chidi.eze@mamankechis.example", "guessed"),
    ],
    "linguabridge.example": [
        ("Pierre Dossou", "Director", "pierre@linguabridge.example", "found"),
        ("Aline Kpodar", "Head of Admissions", "aline.kpodar@linguabridge.example", "guessed"),
    ],
}
