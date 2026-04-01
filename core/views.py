from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from .models import UserProfile
import google.generativeai as genai
import os
from decimal import Decimal

# Configure Gemini safely
gemini_model = None
api_key = os.getenv('GEMINI_API_KEY')
if api_key:
    genai.configure(api_key=api_key)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')


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
    last_choice = levels[-1]  # always get the latest input

    # ==================== REGISTRATION ====================
    if not user or not user.name or not user.pin_hash:
        if len(levels) == 1 and action == "1":
            return "CON Enter your full name:"
        if len(levels) == 2:   # Name entered
            name = levels[1].strip()
            if len(name) < 3:
                return "CON Name too short. Enter full name again:"
            UserProfile.objects.create(phone_number=phone_number, name=name)
            return "CON Name saved!\nEnter 4-digit PIN:"
        if len(levels) == 3:   # PIN entered
            pin_hash = levels[2]
            if len(pin_hash) != 4 or not pin_hash.isdigit():
                return "CON Invalid PIN. Enter 4 digits only:"
            user = UserProfile.objects.get(phone_number=phone_number)
            user.set_pin(pin_hash)
            user.save()
            return "CON Registration successful!\n Set Initial Budget"

    # ==================== SET INITIAL BUDGET ====================
    if user and user.total_balance == 0:
        if len(levels) == 0 and action == "1":
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

    # ==================== MAIN MENU ====================
    if user and user.total_balance > 0:
        # Determine if user is at main menu (first level after login)
        is_main_menu = len(levels) == 1

        if last_choice == "0":
            if is_main_menu:
                return "END You have been logged out. Dial again to use PesaShield."
            else:
                return show_main_menu(user)

        if last_choice == "1":
            return check_balance(user)
        elif last_choice == "2":
            return view_budget(user)
        elif last_choice == "3":
            return "CON Log Expense\nExample: Food 300 or Matatu 100"
        elif last_choice == "4":
            return "CON Adjust Budget (coming soon)"
        elif last_choice == "5":
            return "CON Get AI Advice\nReply with expense or question"
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



def get_gemini_advice(text: str, user=None):
    if not gemini_model:
        return "AI service is currently unavailable."
    prompt = f"You are a helpful Kenyan student budget guardian. Expense: '{text}'. Suggest category and one short saving tip."
    try:
        response = gemini_model.generate_content(prompt)
        return response.text.strip()[:250]
    except:
        return "Logged as Food. Tip: Buy from mama mboga in bulk."