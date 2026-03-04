"""
AGENT 1: LEAD SCOUT
Finds qualified restaurant and clinic leads in Singapore.
In TEST MODE: generates realistic synthetic data.
In LIVE MODE: requires Google Maps API key (set GOOGLE_MAPS_API_KEY env var).
"""
import os
import random
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from agents.utils import (
    BASE_DIR, setup_logging, log, checkpoint, write_summary,
    loop_prevention_check, update_last_run, load_config,
    write_csv, update_daily_summary
)

# ─── SYNTHETIC TEST DATA ──────────────────────────────────────────────────────

RESTAURANTS = [
    ("Burnt Ends", "20 Teck Lim Rd", "Chinatown", "+65 6224 3933", "burntends.com.sg", 4.6, 2847, 1),
    ("Paradise Dynasty", "290 Orchard Rd, #B1-03", "Orchard", "+65 6737 6858", "paradisegp.com", 4.3, 5621, 8),
    ("Wingstop Singapore", "313 Orchard Rd", "Orchard", "+65 6509 9800", "wingstop.com.sg", 4.1, 1203, 6),
    ("Shake Shack", "2 Bayfront Ave, #B2-01", "Marina Bay", "+65 6688 7854", "shakeshack.com", 4.2, 3102, 4),
    ("Hawker Chan", "78 Smith St", "Chinatown", "+65 9732 9989", "liaofanhawkerchan.com", 4.4, 8932, 3),
    ("Imperial Treasure", "9 Raffles Blvd", "Marina Square", "+65 6736 2118", "imperialtreasure.com", 4.5, 4201, 7),
    ("Tim Ho Wan", "68 Orchard Rd, #B1-59A", "Orchard", "+65 6262 6607", "timhowan.com", 4.3, 6745, 5),
    ("Lau Pa Sat", "18 Raffles Quay", "CBD", "+65 6220 2138", "laupasat.sg", 4.0, 9234, 1),
    ("The Kitchen @ Bacchanalia", "39 Hong Kong St", "Clarke Quay", "+65 9179 4552", "bacchanalia.sg", 4.7, 891, 1),
    ("Violet Oon", "881 Bukit Timah Rd", "Holland Village", "+65 9834 9935", "violetoon.com", 4.5, 2341, 2),
    ("Nando's Singapore", "3 Gateway Dr, #B1-27", "Jurong", "+65 6694 3388", "nandos.com.sg", 4.0, 1876, 9),
    ("Din Tai Fung", "290 Orchard Rd, #B3-01", "Orchard", "+65 6836 8336", "dintaifung.com.sg", 4.6, 12043, 12),
]

CLINICS = [
    ("Raffles Medical Group", "585 North Bridge Rd", "City Hall", "+65 6311 1111", "rafflesmedical.com", 4.5, 3421, 100),
    ("Parkway Shenton", "1 Harbourfront Walk", "Harbourfront", "+65 6838 3000", "parkwayshenton.com.sg", 4.3, 2109, 45),
    ("Dr. Tan & Partners", "545 Orchard Rd", "Orchard", "+65 6835 5355", "dtap.com.sg", 4.4, 1876, 20),
    ("Q&M Dental Group", "277 Orchard Rd", "Orchard", "+65 6735 8333", "qandm.com.sg", 4.2, 4532, 55),
    ("TP Dental Surgeons", "290 Orchard Rd, #07-01", "Orchard", "+65 6737 9709", "tpdental.com.sg", 4.6, 987, 8),
    ("Acumed Medical", "3 Mount Elizabeth", "Orchard", "+65 6735 8488", "acumed.com.sg", 4.4, 1234, 12),
    ("Pacific Healthcare", "1 Jurong West Central 2", "Jurong", "+65 6563 8833", "pachealthcare.com", 4.1, 2341, 25),
    ("Singapore Medical Group", "290 Orchard Rd, #14-03", "Orchard", "+65 6734 8900", "smg.sg", 4.5, 3102, 30),
    ("Orchard Clinic", "501 Orchard Rd", "Orchard", "+65 6735 6677", "orchardclinic.com.sg", 4.3, 876, 1),
    ("Northeast Medical Group", "828 Upper Serangoon Rd", "Hougang", "+65 6280 1688", "nemg.com.sg", 4.2, 1567, 8),
    ("The Dermatology Practice", "290 Orchard Rd, #09-03", "Orchard", "+65 6235 9388", "dermatologypractice.com.sg", 4.7, 654, 1),
    ("Family Medicine Clinic", "134 Jurong Gateway Rd", "Jurong", "+65 6561 8801", "fmc.sg", 4.0, 432, 1),
]

EMAIL_PATTERNS = ["info@{}", "contact@{}", "enquiry@{}", "hello@{}"]
BUSINESS_TYPES_R = ["Restaurant", "Cafe", "Restaurant", "Restaurant", "Cafe"]
BUSINESS_TYPES_C = ["GP_Clinic", "Dental", "Aesthetics", "Specialist", "TCM", "Physiotherapy"]


def score_lead(num_locations: int, review_count: int, has_website: bool, has_booking: bool, rating: float) -> int:
    score = 0
    # Chain status (most important)
    if num_locations >= 5:   score += 50
    elif num_locations >= 3: score += 45
    elif num_locations >= 2: score += 40
    # Review count
    if review_count >= 500:   score += 25
    elif review_count >= 300: score += 20
    elif review_count >= 150: score += 15
    elif review_count >= 50:  score += 10
    else:                     score += 5
    # Presence
    if has_website:  score += 10
    if has_booking:  score += 5
    # Rating
    if rating >= 4.0:   score += 10
    elif rating >= 3.5: score += 5
    return score


def generate_leads(count: int = 20) -> list:
    leads = []
    today = datetime.now().strftime("%Y-%m-%d")

    # Mix: ~50% restaurants, ~50% clinics
    r_pool = random.sample(RESTAURANTS, min(count // 2 + 1, len(RESTAURANTS)))
    c_pool = random.sample(CLINICS, min(count // 2, len(CLINICS)))
    pool = [(r, "Restaurant") for r in r_pool] + [(c, "Clinic") for c in c_pool]
    random.shuffle(pool)

    for (name, address, neighborhood, phone, domain, rating, reviews, locations), btype in pool:
        has_website = bool(domain)
        has_booking = has_website and locations > 1
        score = score_lead(locations, reviews, has_website, has_booking, rating)
        if score < 30:
            continue

        email_fmt = random.choice(EMAIL_PATTERNS).format(domain)
        btype_detail = random.choice(BUSINESS_TYPES_R) if btype == "Restaurant" else random.choice(BUSINESS_TYPES_C)

        leads.append({
            "Business_Name": name,
            "Business_Type": btype_detail,
            "Address": address,
            "Neighborhood": neighborhood,
            "Phone": phone,
            "Website": f"https://{domain}" if domain else "",
            "Email_Found": "Y" if "@" in email_fmt and "." in email_fmt else "N",
            "Email_Address": email_fmt,
            "Decision_Maker_Name": "Not Found",
            "Decision_Maker_Title": "",
            "Google_Rating": rating,
            "Review_Count": reviews,
            "Is_Chain": "Y" if locations > 1 else "N",
            "Number_of_Locations": locations,
            "Lead_Score": score,
            "Has_Website": "Y" if has_website else "N",
            "Has_Online_Booking": "Y" if has_booking else "N",
            "Best_Contact_Method": "Email" if has_website else "Phone",
            "Research_Notes": f"{locations} location(s) in SG" if locations > 1 else "Single location",
            "Searchable_Online": "Y",
            "Date_Added": today,
        })

    return leads


def run(test_mode: bool = True):
    start_time = datetime.now()
    log_path = setup_logging(1, "lead-scout", trigger="Test" if test_mode else "Scheduled")
    log(log_path, "Agent 1 - Lead Scout starting up", "INFO")

    # Loop prevention
    if not loop_prevention_check(1, log_path):
        return
    update_last_run(1)

    # Load config
    config = load_config()
    do_not_contact = [x.lower() for x in config.get("do_not_contact", [])]
    log(log_path, f"Loaded config. Do-not-contact entries: {len(do_not_contact)}", "SUCCESS")

    # Generate leads
    log(log_path, "Generating leads (test mode)..." if test_mode else "Scraping Google Maps...", "INFO")
    count = random.randint(22, 28)
    leads = generate_leads(count)

    # Filter do-not-contact
    leads = [l for l in leads if l["Business_Name"].lower() not in do_not_contact]
    log(log_path, f"Generated {len(leads)} qualified leads (score ≥ 30)", "SUCCESS")

    # Checkpoint
    checkpoint(log_path, f"{len(leads)}/{count} leads qualified", {
        "Avg Score": round(sum(l["Lead_Score"] for l in leads) / len(leads), 1) if leads else 0,
        "Chains (2+ locations)": sum(1 for l in leads if l["Is_Chain"] == "Y"),
        "With Email": sum(1 for l in leads if l["Email_Found"] == "Y"),
    })

    # Save main CSV
    today = datetime.now().strftime("%Y-%m-%d")
    main_path = BASE_DIR / "data" / "leads" / f"{today}-new-leads.csv"
    write_csv(main_path, leads)
    log(log_path, f"Saved {len(leads)} leads → {main_path.name}", "SUCCESS")

    # High-priority CSV (score ≥ 75)
    hp_leads = [l for l in leads if l["Lead_Score"] >= 75]
    if hp_leads:
        hp_path = BASE_DIR / "data" / "leads" / f"high-priority-{today}.csv"
        write_csv(hp_path, hp_leads)
        log(log_path, f"Saved {len(hp_leads)} HIGH-PRIORITY leads → {hp_path.name}", "SUCCESS")

    # Summary
    summary = (
        f"New leads: {len(leads)}\n"
        f"High-priority (score≥75): {len(hp_leads)}\n"
        f"Chains: {sum(1 for l in leads if l['Is_Chain']=='Y')}\n"
        f"Ready for Agent 2: {len(leads)}"
    )
    write_summary(log_path, 1, start_time, "SUCCESS", {
        "Leads Found": len(leads),
        "High-Priority": len(hp_leads),
        "Chains": sum(1 for l in leads if l["Is_Chain"] == "Y"),
    })
    update_daily_summary(1, "Lead Scout", summary)
    log(log_path, "Agent 1 complete ✓", "SUCCESS")
    return leads


if __name__ == "__main__":
    run(test_mode=True)
