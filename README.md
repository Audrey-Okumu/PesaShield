# PesaShield 💰

**A simple USSD-based budgeting assistant for Kenyan public university students**

Helps students manage their HELB upkeep money wisely — track expenses, get automatic budget splits, receive smart warnings, and stay in control without needing data or a smartphone app.

---

## 🎯 Problem It Solves

- Once the money hits M-Pesa, it vanishes quickly due to mismanagement.
- Most students use feature phones or have limited data on campus.
- No easy way to track spending or get gentle reminders before money finishes.

**PesaShield** turns passive HELB inflows into proactive money management using just a USSD code (`*shortcode#`).

---

## ✨ Key Features

- **Simple Registration** — Name + 4-digit PIN
- **Automatic Budget Split** — 40% Food | 25% Accommodation | 15% Transport | 10% Savings | 10% Other
- **Log Expenses** — Type `Food 300`, `Matatu 100`, `Mama mboga 250`
- **Auto Deduction** — Budget updates instantly after every expense
- **Smart Warnings** — Alerts when categories are running low
- **Adjust Budget** — Manually change amounts in any category
- **Guardian Advice** — Get helpful tips and category suggestions
- **Check Balance & View Budget** — Real-time overview
- **Works on any phone** — Fully USSD-based (no data required)

---

## 🛠 Tech Stack

- **Backend**: Django (Python)
- **Database**: PostgreSQL
- **USSD Integration**: Africa’s Talking Sandbox
- **AI Advice**: Rule-based Guardian logic (Gemini fallback available)
- **Deployment (Demo)**: Local + ngrok

---

## 🚀 How to Run Locally

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/pesashield.git
   cd pesashield
   ```
2. Activate virtual environment:
```bash
venv\Scripts\activate     # Windows
# source venv/bin/activate  # Mac/Linux
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables (.env file):
```env
GEMINI_API_KEY=your_key_here
AT_USERNAME=sandbox
AT_API_KEY=your_africastalking_key
```

5. Run migrations and start server:
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```

6. Expose with ngrok:
```bash
ngrok http 8000
```

7. Use Africa’s Talking USSD Simulator with the ngrok URL.


## 📱 Demo Flow

Dial USSD code
Register (Name + PIN)
Set initial HELB amount (e.g. 25000)
Login with PIN
Use Main Menu:
1 → Check Balance
2 → View Budget
3 → Log Expense
4 → Adjust Budget
5 → Get Guardian Advice
0 → Logout



## 🎓 Target Users

Kenyan university students
Students using feature phones
Students who want simple financial control without apps or data bundles