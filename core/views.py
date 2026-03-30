from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import hashlib
from .models import UserProfile
import google.generativeai as genai
import os

# Configure Gemini (free)
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

@csrf_exempt
def ussd_callback(request):
    if request.method == 'POST':
        session_id = request.POST.get('sessionId')
        service_code = request.POST.get('serviceCode')
        phone_number = request.POST.get('phoneNumber')
        text = request.POST.get('text', '')  # User input (empty on first call)

        # Get or create user profile
        try:
            user = UserProfile.objects.get(phone_number=phone_number)
        except UserProfile.DoesNotExist:
            user = None

        response = handle_ussd_flow(phone_number, text, user)
        return HttpResponse(response, content_type='text/plain')
    
    return HttpResponse("END Invalid request", content_type='text/plain')


def handle_ussd_flow(phone_number, text, user):
    """Main logic for USSD flow"""
    if not text:  # First request in session
        if user and user.name:
            return "CON Welcome back " + user.name + "\n1. Enter PIN to login"
        else:
            return "CON Welcome to PesaShield\n1. Register (New User)"

    # Split text for multi-step navigation (e.g., "1*Audrey*1234")
    levels = text.split('*')
    current_level = levels[0]

    # Registration flow
    if not user or not user.name:
        if len(levels) == 1 and current_level == "1":
            return "CON Enter your full name:"
        elif len(levels) == 2:
            name = levels[1].strip()
            if len(name) < 3:
                return "CON Name too short. Enter your full name:"
            # Create user with name
            user = UserProfile.objects.create(
                phone_number=phone_number,
                name=name
            )
            return "CON Name saved: " + name + "\nEnter 4-digit PIN to set:"
        elif len(levels) == 3:
            pin = levels[2]
            if len(pin) != 4 or not pin.isdigit():
                return "CON Invalid PIN. Enter 4 digits only:"
            user.set_pin(pin)
            user.save()
            # Auto-create initial budget (user will set total later)
            return "END Registration successful!\nYou can now login with your PIN."
    
    # Login flow
    if user and not user.name:  # Should not happen
        pass

    if len(levels) == 1 and current_level == "1" and user:
        return "CON Enter your 4-digit PIN:"

    if len(levels) == 2 and user:
        entered_pin = levels[1]
        if user.check_pin(entered_pin):
            return show_main_menu()
        else:
            return "END Incorrect PIN. Try again later."

    return "END Invalid option. Session ended."


def show_main_menu():
    """Main menu after successful login"""
    menu = "CON PesaShield Main Menu\n"
    menu += "1. Check Balance\n"
    menu += "2. View Budget\n"
    menu += "3. Log Expense\n"
    menu += "4. Adjust Budget\n"
    menu += "5. Get AI Advice\n"
    menu += "0. Logout"
    return menu


# Helper for AI 
def get_gemini_advice(expense_text: str, current_budget: dict) -> str:
    """Free Gemini AI for smart categorization and tips"""
    prompt = f"""
    You are PesaShield Guardian, a friendly financial advisor for Kenyan university students.
    Expense: "{expense_text}"
    Current budget context: Food {current_budget.get('food', 0)}, Accommodation {current_budget.get('accommodation', 0)}, etc.

    Respond in short, simple Kenyan student English/Swahili mix (max 2-3 lines):
    - Suggest best category (Food, Accommodation, Transport, Savings, Other)
    - Give one practical tip
    Keep it encouraging and realistic.
    """
    try:
        response = gemini_model.generate_content(prompt)
        return response.text.strip()[:300]  # Keep short for USSD
    except Exception:
        # Fallback if API fails
        return "Logged as Food. Tip: Buy in bulk from mama mboga to save money."