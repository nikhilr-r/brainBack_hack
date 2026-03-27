"""
config/knowledge_base.py
------------------------
Bank knowledge base — all FAQs and policy documents.
Add / edit entries here to update what the bot knows.
No code changes needed — just add strings to BANK_KNOWLEDGE.

Format: Plain English sentences (the embedder handles retrieval).
Tip: One fact per entry. Don't merge unrelated facts.
"""

BANK_KNOWLEDGE = [

    # ── Savings Account ──────────────────────────────────────────
    "Savings account interest rate is 2.70% per year for balance below 1 lakh rupees, "
    "and 3.00% per year for balance above 1 lakh rupees.",

    "To open a personal bank account or savings account you need: Aadhaar card, PAN card, one passport-size "
    "photograph, and a minimum initial deposit of Rs. 500. This is the standard account "
    "for retail individuals.",

    "Minimum balance for savings account is Rs. 1000 in urban branches, Rs. 500 in "
    "semi-urban branches, and Rs. 250 in rural branches. "
    "Non-maintenance charge is Rs. 100 per quarter.",

    "Zero balance BSBD account is available for all Indian citizens. No minimum balance "
    "is required. Basic banking services are completely free.",

    "Pradhan Mantri Jan Dhan Yojana (PMJDY) Jan Dhan account has zero minimum balance. "
    "Only Aadhaar card is needed. It comes with a free RuPay debit card and "
    "Rs. 1 lakh accidental insurance. Also known as Jandhan Yojna.",

    "Salary account has zero minimum balance requirement. It gets converted to a regular "
    "savings account if no salary is credited for 3 consecutive months.",

    # ── Fixed Deposit ────────────────────────────────────────────
    "Fixed Deposit interest rates: 7 to 45 days is 3.50%, 46 to 179 days is 4.50%, "
    "180 days to 1 year is 5.75%, 1 year to 2 years is 6.80%, "
    "2 to 3 years is 7.00%, above 3 years is 6.50%.",

    "Senior citizens get 0.50% extra interest on all Fixed Deposits over regular rates. "
    "Age proof like Aadhaar card or voter ID is required.",

    "Minimum amount to open a Fixed Deposit is Rs. 1000. There is no maximum limit. "
    "FD can be opened for any period from 7 days to 10 years.",

    "Premature withdrawal of Fixed Deposit is allowed. A penalty of 1% is charged on "
    "the interest rate applicable for the period the deposit was held.",

    "TDS is deducted on FD interest above Rs. 40,000 per year. Submit Form 15G "
    "(below 60 years) or Form 15H (senior citizens) to avoid TDS if income is below "
    "taxable limit.",

    "Auto-renewal of Fixed Deposit is available. You can choose auto-renewal of "
    "principal only, or principal plus interest, at the time of FD opening.",

    # ── Recurring Deposit ────────────────────────────────────────
    "Recurring Deposit minimum installment is Rs. 100 per month. Maximum tenure is "
    "10 years. Interest rate is same as Fixed Deposit rates.",

    "Missed Recurring Deposit installment attracts a penalty of Rs. 1.50 per Rs. 100 "
    "per month for general customers.",

    # ── Home Loan ────────────────────────────────────────────────
    "Home loan interest rate starts at 8.40% per year. Maximum loan tenure is 30 years. "
    "The bank finances up to 90% of the property value.",

    "Documents for home loan: Aadhaar card, PAN card, last 3 months salary slips, "
    "last 6 months bank statements, property documents, and Form 16.",

    "Home loan EMI example: For Rs. 30 lakh loan at 8.40% for 20 years, "
    "monthly EMI is approximately Rs. 25,900.",

    # ── Personal Loan ────────────────────────────────────────────
    "Personal loan interest rate is 10.50% to 14.00% per year. Maximum amount is "
    "Rs. 10 lakh. Tenure up to 5 years. Income proof and KYC documents required.",

    "Personal loan can be processed within 2 to 3 working days if all documents are "
    "in order. No collateral or guarantor is required.",

    # ── Education Loan ───────────────────────────────────────────
    "Education loan is available for studies in India and abroad. Interest rate from "
    "8.85% per year. Maximum Rs. 10 lakh for studies in India and Rs. 20 lakh abroad.",

    "Education loan requires: Aadhaar card, admission letter from institution, "
    "fee structure, mark sheets, and income proof of co-applicant parent.",

    # ── Gold Loan ────────────────────────────────────────────────
    "Gold loan is available at 75% of the gold value. Interest rate is 9.50% per year. "
    "Maximum tenure is 12 months. No income proof is required for gold loan.",

    # ── Agricultural / Government Schemes ────────────────────────
    "Kisan Credit Card (KCC) loan is available for farmers at 7% per year with "
    "government subsidy. Maximum amount is Rs. 3 lakh. "
    "Requires land records and Aadhaar card.",

    "Mudra loan under Pradhan Mantri Mudra Yojana: Shishu category up to Rs. 50,000, "
    "Kishor category up to Rs. 5 lakh, Tarun category up to Rs. 10 lakh. "
    "No collateral needed.",

    # ── Government Savings / Insurance Schemes ───────────────────
    "Sukanya Samriddhi Yojana (SSY) is a government savings scheme for the girl child. "
    "Interest rate is 8.0% per year. Minimum deposit Rs. 250 per year. "
    "Maximum deposit Rs. 1.5 lakh per year. Account matures when the girl turns 21. "
    "Also known as Sukanya Yojna scheme.",

    "Atal Pension Yojana (APY) provides a guaranteed monthly pension of Rs. 1000 to Rs. 5000 "
    "after age 60. Open to all citizens between 18 and 40 years of age. "
    "Government co-contributes 50% for eligible subscribers.",

    "Pradhan Mantri Jeevan Jyoti Bima Yojana (PMJJBY) provides Rs. 2 lakh life insurance "
    "cover at just Rs. 436 per year. Available for account holders aged 18 to 50.",

    "Pradhan Mantri Suraksha Bima Yojana (PMSBY) provides Rs. 2 lakh accidental death "
    "and disability insurance at just Rs. 20 per year. For ages 18 to 70.",

    "National Pension Scheme (NPS) allows retirement savings with tax benefits under "
    "Section 80CCD. Minimum contribution Rs. 500 per year. Withdrawal at age 60.",

    "Public Provident Fund (PPF) account has an interest rate of 7.1% per year. "
    "Minimum deposit Rs. 500 per year, maximum Rs. 1.5 lakh. Lock-in period is 15 years. "
    "Tax-free returns under Section 80C.",

    "Senior Citizen Savings Scheme (SCSS) offers 8.2% interest per year. "
    "Minimum deposit Rs. 1000, maximum Rs. 30 lakh. Tenure is 5 years, extendable by 3 years. "
    "Available for citizens aged 60 and above.",

    "PM Vishwakarma Yojana provides loans up to Rs. 3 lakh at 5% interest for traditional "
    "artisans and craftsmen. Includes skill training and toolkit allowance of Rs. 15,000.",

    "Stand Up India scheme provides loans from Rs. 10 lakh to Rs. 1 crore for SC/ST and "
    "women entrepreneurs starting a new enterprise. At least one SC/ST borrower and one "
    "woman borrower per branch.",

    "PM SVANidhi scheme provides affordable working capital loan of Rs. 10,000 to "
    "street vendors. Interest subsidy of 7% per year. No collateral required.",

    "Mahila Samman Savings Certificate offers 7.5% interest per year for women. "
    "Minimum deposit Rs. 1000, maximum Rs. 2 lakh. Tenure is 2 years. "
    "Partial withdrawal allowed after 1 year.",

    # ── Account Opening Requirements ─────────────────────────────
    "To open a commercial business current account you need: PAN card, business address proof, GST certificate, "
    "partnership deed or incorporation certificate, and initial deposit of Rs. 10,000.",

    "To open an account for a minor child, the parent or guardian Aadhaar card is needed "
    "along with the birth certificate of the child. No minimum balance for minor accounts.",

    "NRI account types include NRE (Non-Resident External) and NRO (Non-Resident Ordinary). "
    "NRE account is fully repatriable and tax-free in India. NRO account is non-repatriable.",

    # ── Loan Schemes ─────────────────────────────────────────────
    "Vehicle loan is available for new and used vehicles at 8.70% interest rate per year. "
    "Financing up to 85% of the on-road price. Maximum tenure 7 years.",

    "Loan against property is available at 9.40% interest rate. "
    "Up to 60% of property market value can be financed. Maximum tenure 15 years.",

    "Overdraft facility is available on Fixed Deposits up to 90% of the FD value. "
    "Interest rate is FD rate plus 1%. No separate documentation is required.",

    # ── ATM and Cards ────────────────────────────────────────────
    "ATM daily cash withdrawal limit is Rs. 40,000 for Classic debit cards and "
    "Rs. 1,00,000 for Platinum debit cards.",

    "To block a lost or stolen debit card immediately: call 24x7 helpline "
    "1800-XXX-XXXX (toll free), or use the mobile banking app, or visit the branch.",

    "ATM PIN can be changed at any of our ATMs by selecting the PIN Change option, "
    "or at the branch by submitting a written request form.",

    "Free ATM transactions per month: 5 free at our own ATMs, 3 free at other bank ATMs. "
    "After the free limit, Rs. 21 per transaction is charged.",

    "Debit card annual fee: Rs. 150 plus GST for Classic card, Rs. 250 plus GST for "
    "Platinum card. The first year fee is waived for new accounts.",

    # ── Digital Banking ──────────────────────────────────────────
    "To check account balance: use ATM, net banking website, mobile banking app, "
    "missed call to 09XXXXXXXXX, or SMS BAL to 56XXX.",

    "NEFT and RTGS money transfers are free for online transactions. "
    "For branch NEFT: up to Rs. 10,000 costs Rs. 2 plus GST.",

    "UPI payments are completely free for all transactions. Daily UPI limit is Rs. 1 lakh. "
    "For higher limits, visit the branch.",

    "To register for mobile banking: visit any branch with Aadhaar card, "
    "or register online using account number and registered mobile number.",

    # ── KYC and Documents ────────────────────────────────────────
    "Accepted KYC documents: Aadhaar card, PAN card, Voter ID card, Passport, "
    "or Driving License. One identity proof and one address proof is required.",

    "KYC update is mandatory every 2 years for high-risk customers and every "
    "8 to 10 years for low-risk customers. Branch visit is required in person.",

    "Nominee addition or change can be done at the branch by submitting Form DA1 "
    "along with the Aadhaar card of the nominee.",

    # ── Branch Services ──────────────────────────────────────────
    "Branch timings are Monday to Friday: 10 AM to 4 PM. "
    "Saturday: 10 AM to 1 PM. Closed on Sundays and all bank holidays.",

    "Cheque book request can be submitted at the branch counter, or through the mobile "
    "banking app. Delivery takes 3 to 5 working days.",

    "Locker facility is available at select branches. Annual rent: "
    "small locker Rs. 1000, medium locker Rs. 3000, large locker Rs. 8000.",

    "Demand Draft charges: up to Rs. 10,000 is Rs. 25; Rs. 10,001 to Rs. 1 lakh is "
    "Rs. 50; above Rs. 1 lakh is Rs. 3 per thousand, minimum Rs. 75.",

    # ── Grievance ────────────────────────────────────────────────
    "To register a complaint: visit the branch, call 1800-XXX-XXXX (toll free), "
    "email grievance@bank.in, or use the mobile banking app. "
    "Response is given within 7 working days.",

    "Banking Ombudsman of Reserve Bank of India can be approached if complaint is not "
    "resolved within 30 days. This service is completely free.",
]
