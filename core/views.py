from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from .models import UserProfile
import os
from decimal import Decimal
from google import genai

# Configure Gemini 
gemini_client = None
api_key = os.getenv('GEMINI_API_KEY')
if api_key:
    try:
        gemini_client = genai.Client(api_key=api_key)
        print("✅ Gemini API  configured successfully")
    except Exception as e:
        print(f"❌ Gemini configuration failed: {e}")
        gemini_client = None
else:
    print("❌ GEMINI_API_KEY not found in .env")


@csrf_exempt
def ussd_callback(request):
    if request.method == 'POST':
        phone_number = request.POST.get('phoneNumber')
        text = request.POST.get('text', '').strip()

        if not phone_number:
            return HttpResponse("END Missing phone number", content_type='text/plain')

        user = UserProfile.objects.filter(phone_number=phone_number).first()

        response = handle_ussd_flow(phone_number, text, user)
        return HttpResponse(response, content_type='text/plain')

    return HttpResponse("END Invalid request", content_type='text/plain')


def handle_ussd_flow(phone_number: str, text: str, user):
    if not text:  # First screen when user dials
        if user and user.name:
            if user.total_balance > 0:
                return f"CON Welcome back {user.name}!\n1. Enter 4-digit PIN to login"
            else:
                return f"CON Welcome {user.name}!\n1. Set Initial Budget"
        return "CON Welcome to PesaShield\n1. Register (New User)"

    levels = text.split('*')
    action = levels[0]
    last_choice = levels[-1]

    # ==================== REGISTRATION ====================
    if not user or not user.name or not user.pin_hash:
        if len(levels) == 1 and action == "1":
            return "CON Enter your full name:"
        if len(levels) == 2:  # Name entered
            name = levels[1].strip()
            if len(name) < 3:
                return "CON Name too short. Enter full name again:"
            UserProfile.objects.create(phone_number=phone_number, name=name)
            return "CON Name saved!\nEnter 4-digit PIN:"
        if len(levels) == 3:  # PIN entered
            pin_hash = levels[2]
            if len(pin_hash) != 4 or not pin_hash.isdigit():
                return "CON Invalid PIN. Enter 4 digits only:"
            user = UserProfile.objects.get(phone_number=phone_number)
            user.set_pin(pin_hash)
            user.save()
            return "CON Registration successful!\n1. Set Initial Budget"

    # ==================== SET INITIAL BUDGET ====================
    if user and user.total_balance == 0:
        if len(levels) == 1 and action == "1":
            return "CON Enter total HELB/upkeep amount (e.g. 25000):"
        if len(levels) >= 2:
            try:
                total = Decimal(levels[-1])
                if total <= 0:
                    return "CON Amount must be greater than 0. Try again:"

                user.total_balance = total
                user.food = total * Decimal('0.40')
                user.accommodation = total * Decimal('0.25')
                user.transport = total * Decimal('0.15')
                user.savings = total * Decimal('0.10')
                user.other = total * Decimal('0.10')
                user.save()

                return show_main_menu(user, message=f"Budget setup successful! Total: KSh {total:.0f}")
            except:
                return "CON Invalid amount. Enter numbers only (e.g. 25000):"

    # ==================== LOGIN ====================
    if user and user.total_balance > 0:
        if len(levels) == 1 and action == "1":
            return "CON Enter your 4-digit PIN:"
        if len(levels) == 2 and user.check_pin(levels[1]):
            return show_main_menu(user)

    # ==================== MAIN MENU (Step 6 updates here) ====================
    if user and user.total_balance > 0:
        # If user presses "0"
        if last_choice == "0":
            # If user is at main menu (first level is empty or "0"), log them out
            if len(levels) <= 2:
                return "END You have been logged out. Dial again to use PesaShield."
            else:
                # If user is in a submenu, go back to main menu
                return show_main_menu(user)
        if "4" in levels:
            return handle_adjust_budget(user, levels)

        if last_choice == "1":
            return check_balance(user)
        elif last_choice == "2":
            return view_budget(user)
        elif "3" in levels:
            expense_index = levels.index("3")
            if len(levels) == expense_index + 1:
                return ("CON Log Expense\n"
                        "Example: Food 300 or Matatu 100\n"
                        "0. Back to Menu")
            # User entered expense after 3
            expense_text = levels[expense_index + 1]
            return log_expense(user, expense_text)

        elif "5" in levels:
            advice_index = levels.index("5")

            # User has only selected menu option 5
            if len(levels) == advice_index + 1:
                return ("CON Get AI Advice\n"
                "Reply with expense or question\n"
                "Example: I spent too much on food this week\n"
                "0. Back to Menu")

            # User entered a question after selecting 5
            advice_text = levels[advice_index + 1].strip()

            if not advice_text:
                return ("CON Please enter a question or expense.\n"
                "Example: I spent too much on food this week\n"
                "0. Back to Menu")

            ai_response = get_gemini_advice(advice_text, user)
            return f"CON {ai_response}\n\n0. Back to Menu"
        else:
            return show_main_menu(user)

    return "END Invalid option. Please dial the code again."


def show_main_menu(user, message=None):
    header = f"CON {message}\n\n" if message else "CON PesaShield Main Menu\n"
    return (f"{header}{user.name}\n"
            "1. Check Balance\n"
            "2. View Budget\n"
            "3. Log Expense\n"
            "4. Adjust Budget\n"
            "5. Get AI Advice\n"
            "0. Logout")


def check_balance(user):
    total_left = user.food + user.accommodation + user.transport + user.savings + user.other
    return (f"CON Current Balance\n"
            f"Total Left: KSh {total_left:.0f}\n\n"
            f"Food: KSh {user.food:.0f}\n"
            f"Accommodation: KSh {user.accommodation:.0f}\n"
            f"Transport: KSh {user.transport:.0f}\n"
            f"Savings: KSh {user.savings:.0f}\n"
            f"Other: KSh {user.other:.0f}\n\n"
            "0. Back to Menu")


def view_budget(user):
    return (f"CON Your Budget Breakdown\n\n"
            f"Food (40%): KSh {user.food:.0f}\n"
            f"Accommodation (25%): KSh {user.accommodation:.0f}\n"
            f"Transport (15%): KSh {user.transport:.0f}\n"
            f"Savings (10%): KSh {user.savings:.0f}\n"
            f"Other (10%): KSh {user.other:.0f}\n\n"
            "0. Back to Menu")


# ====================== LOG EXPENSE ======================
def log_expense(user, expense_text: str):
    """Log expense, auto-deduct from category, and show warnings"""
    if not expense_text or ' ' not in expense_text:
        return "CON Invalid format.\nUse: Food 300\nExample: Matatu 100\n0. Back to Menu"

    try:
        parts = expense_text.rsplit(' ', 1)
        item = parts[0].strip().lower()
        amount = Decimal(parts[1])

        if amount <= 0:
            return "CON Amount must be greater than 0\n0. Back to Menu"

        category = detect_category(item)
        field_name = get_category_field(category)

        current = getattr(user, field_name, Decimal('0'))

        if current < amount:
            return f"CON Not enough in {category}!\nOnly KSh {current:.0f} left.\n0. Back to Menu"

        # Auto deduct
        setattr(user, field_name, current - amount)
        user.save()

        warning = get_low_budget_warning(user, field_name)

        msg = f"CON Logged successfully!\n{category}: -KSh {amount:.0f}\n"
        msg += f"{category} left: KSh {getattr(user, field_name):.0f}\n"

        if warning:
            msg += f"\n⚠️ {warning}"

        msg += "\n0. Back to Menu"
        return msg

    except:
        return "CON Invalid format.\nUse: Food 300 or Mama mboga 150\n0. Back to Menu"


def detect_category(text: str) -> str:
    text = text.lower()
    if any(k in text for k in ['food', 'mboga', 'chai', 'mandazi', 'lunch', 'dinner', 'kuinama']):
        return "Food"
    if any(k in text for k in ['matatu', 'transport', 'fare', 'boda', 'bus']):
        return "Transport"
    if any(k in text for k in ['hostel', 'rent', 'accommodation', 'room']):
        return "Accommodation"
    if any(k in text for k in ['airtime', 'data']):
        return "Other"
    # Fallback to Gemini AI
    if gemini_client:
        try:
            prompt = f"Classify this expense into one category: Food, Accommodation, Transport, Savings, Other. Expense: '{text}'"
            resp = gemini_client.generate_content(prompt)
            cat = resp.text.strip().lower()
            if 'food' in cat: return "Food"
            if 'accommodation' in cat or 'hostel' in cat: return "Accommodation"
            if 'transport' in cat: return "Transport"
            if 'savings' in cat: return "Savings"
            return "Other"
        except:
            pass
    return "Other"


def get_category_field(category: str) -> str:
    mapping = {
        "Food": "food",
        "Accommodation": "accommodation",
        "Transport": "transport",
        "Savings": "savings",
        "Other": "other"
    }
    return mapping.get(category, "other")


def get_low_budget_warning(user, field_name: str) -> str:
    balance = getattr(user, field_name, Decimal('0'))
    if balance <= 0:
        return "This category is now empty!"
    elif balance < 1000:
        return "Running very low! Spend wisely."
    elif balance < 3000:
        return "Consider spending less here."
    return ""

def handle_adjust_budget(user, levels):
    adjust_index = levels.index("4")
    categories = {
        "1": "Food",
        "2": "Accommodation",
        "3": "Transport",
        "4": "Savings",
        "5": "Other"
    }

    # Step 1: User entered "4" -> show categories
    if len(levels) == adjust_index + 1:
        return ("CON Adjust Budget\n"
                "1. Food\n"
                "2. Accommodation\n"
                "3. Transport\n"
                "4. Savings\n"
                "5. Other\n0. Back to Menu")

    # Step 2: User selects a category -> prompt for new amount
    if len(levels) == adjust_index + 2:
        category_choice = levels[adjust_index + 1]
        if category_choice not in categories:
            return "CON Invalid choice.\n0. Back to Menu"
        cat_name = categories[category_choice]
        current = getattr(user, get_category_field(cat_name), Decimal('0'))
        return (f"CON Adjust {cat_name}\n"
                f"Current: KSh {current:.0f}\n"
                "Enter new amount (e.g., 5000):")

    # Step 3: User enters new amount -> save
    if len(levels) == adjust_index + 3:
        category_choice = levels[adjust_index + 1]
        if category_choice not in categories:
            return "CON Invalid choice.\n0. Back to Menu"
        try:
            new_amount = Decimal(levels[adjust_index + 2])
            if new_amount < 0:
                return "CON Amount cannot be negative.\nEnter a valid amount:"
            cat_name = categories[category_choice]
            field_name = get_category_field(cat_name)
            setattr(user, field_name, new_amount)
            user.save()
            return f"CON {cat_name} updated to KSh {new_amount:.0f}\n0. Back to Menu"
        except:
            return "CON Invalid amount. Enter numbers only.\n0. Back to Menu"

    return "CON Invalid option.\n0. Back to Menu"



def get_gemini_advice(text: str, user=None):
    if not gemini_client:
        return "AI service is currently unavailable. Please try again later."

    prompt = f"""
    You are PesaShield Guardian, a friendly financial advisor for Kenyan university students.
    User input: "{text}"
    
    Respond in short, simple, encouraging Kenyan student style (max 2-3 lines):
    - If it's an expense, suggest the best category and one practical tip.
    - If it's a question, give helpful budgeting advice.
    Use simple English or Sheng if natural.
    """

    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        result = response.text.strip()
        return result[:280] if result else "Tip: Track your spending daily."
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return "Tip: Track your daily spending so HELB money lasts longer. Spend wisely!"