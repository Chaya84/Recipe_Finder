import logging
import tkinter as tk
from tkinter import messagebox, ttk
import requests
import threading
import pandas as pd  # used for nutrition table
import re

# optional matplotlib imports for plotting
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# image handling
from PIL import Image, ImageTk

# theming (CSS-variable-like dictionary)
THEME = {
    'bg': '#f5f5f5',
    'fg': '#333333',
    'accent': '#3498db',
    'card_bg': '#ffffff',
    'font_large': ('Helvetica', 16, 'bold'),
    'font_medium': ('Helvetica', 12),
    'font_small': ('Helvetica', 10),
}

# configure logging
logging.basicConfig(
    filename='app.log',
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s:%(message)s'
)
logger = logging.getLogger(__name__)

API_KEY = "8e5855a362384c3abb341bf0fdfdd959"

recipes_data = []  # store recipes globally
image_label = None
image_photo = None

# filter variable (dropdown)
diet_var = None  # will hold a string like 'None','Vegetarian', etc.

# ui frames and containers
search_frame = None
details_frame = None
results_container = None

details_content = None
nutrition_content = None
nutrition_button = None
back_button = None

details_canvas = None

# login widgets
username_entry = None
password_entry = None
login_frame = None


def search():
    """Start a background thread to fetch recipes for the given ingredients and a selected diet."""
    ingredients = entry.get().strip()
    if not ingredients:
        messagebox.showwarning("Input required", "Please enter at least one ingredient.")
        return

    selected = diet_var.get()
    filters = []
    if selected and selected != "None":
        filters.append(selected.lower())

    logger.info("User search for ingredients=%s diet=%s", ingredients, selected)

    # clear previous cards
    if results_container:
        for w in results_container.winfo_children():
            w.destroy()
    threading.Thread(target=fetch_recipes, args=(ingredients, filters), daemon=True).start()


def fetch_recipes(ingredients, filters=None):
    # Use complexSearch so we can apply diet filters
    url = "https://api.spoonacular.com/recipes/complexSearch"
    params = {"includeIngredients": ingredients, "number": 5, "apiKey": API_KEY}
    if filters:
        # spoonacular expects a single diet string; join comma for readability
        params["diet"] = ",".join(filters)

    logger.debug("Requesting %s with params %s", url, params)

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json().get('results', [])

        global recipes_data
        recipes_data = data
        root.after(0, update_results)
    except Exception as exc:
        logger.exception("Error fetching recipes")
        root.after(0, lambda: messagebox.showerror("Error", f"Error fetching recipes: {exc}"))


def update_results():
    """Populate the results_container with recipe cards for the current recipes_data."""
    if not results_container:
        return
    # clear old cards
    for w in results_container.winfo_children():
        w.destroy()

    # helper to create a single card
    def make_card(index, recipe):
        card = tk.Frame(results_container, bd=1, relief=tk.RIDGE,
                        padx=10, pady=5, bg=THEME['card_bg'])
        title = tk.Label(card, text=recipe.get('title',''),
                         font=THEME['font_medium'], anchor='w', bg=THEME['card_bg'], fg=THEME['fg'])
        title.pack(fill='x')
        btn = tk.Button(card, text="🔍 View Details", fg=THEME['accent'],
                        command=lambda i=index: show_details(i))
        btn.pack(pady=5)
        return card

    # animate each card with slight delay
    for idx, recipe in enumerate(recipes_data):
        def add(i=idx, r=recipe):
            c = make_card(i, r)
            c.pack(fill='x', padx=10, pady=5)
        root.after(idx * 100, add)




def show_details(index):
    show_details_page()
    threading.Thread(target=fetch_details, args=(index,), daemon=True).start()


def fetch_details(index):
    try:
        recipe = recipes_data[index]
        recipe_id = recipe["id"]

        # fetch basic information
        info_url = f"https://api.spoonacular.com/recipes/{recipe_id}/information"
        info_resp = requests.get(info_url, params={"apiKey": API_KEY})
        info_resp.raise_for_status()
        info = info_resp.json()

        # fetch nutrition widget
        nut_url = f"https://api.spoonacular.com/recipes/{recipe_id}/nutritionWidget.json"
        nut_resp = requests.get(nut_url, params={"apiKey": API_KEY})
        nut_resp.raise_for_status()
        nutrition = nut_resp.json()

        root.after(0, lambda: display_details(info, nutrition))
    except Exception as exc:
        root.after(0, lambda: messagebox.showerror("Error", f"Error fetching details: {exc}"))


def display_details(info, nutrition):
    """Fill the details_content frame with recipe info and prepare nutrition data."""
    global image_label, image_photo, last_nutrition, nutrition_button
    last_nutrition = nutrition

    # clear previous widgets
    for w in details_content.winfo_children():
        w.destroy()

    # title
    tk.Label(details_content, text=info.get('title',''), font=THEME['font_large'], fg=THEME['accent']).pack(pady=5)

    # image
    img_url = info.get('image')
    if img_url:
        try:
            resp = requests.get(img_url, stream=True)
            resp.raise_for_status()
            img = Image.open(resp.raw)
            img = img.resize((250, 250))
            image_photo = ImageTk.PhotoImage(img)
            image_label = tk.Label(details_content, image=image_photo)
            image_label.pack(pady=5)
        except Exception as e:
            logger.error("Error loading image: %s", e)

    # ingredients
    tk.Label(details_content, text="Ingredients:", font=('Arial', 12, 'underline')).pack(anchor='w', padx=10)
    for ing in info.get("extendedIngredients", []):
        tk.Label(details_content, text=f"- {ing.get('original','')}").pack(anchor='w', padx=20)

    # instructions
    tk.Label(details_content, text="Instructions:", font=('Arial', 12, 'underline')).pack(anchor='w', padx=10, pady=(10,0))
    instr_raw = info.get("instructions")
    logger.debug("Instructions from API: %s", instr_raw)
    instr = strip_html(instr_raw) if instr_raw else "No instructions available."
    if not instr.strip():
        instr = "No instructions available."

    txt = tk.Text(details_content, height=10, wrap=tk.WORD)
    txt.insert(tk.END, instr)
    txt.config(state=tk.DISABLED)
    txt.pack(fill='both', expand=True, padx=10, pady=5)

    # nutrition button
    nutrition_button = tk.Button(details_content, text="🥗 Nutrition", bg=THEME['accent'], fg='white', command=show_nutrition_only)
    nutrition_button.pack(pady=10)

    logger.info("Displayed details for %s", info.get('title',''))


def plot_nutrition(nutrition, master=None):
    """Plot nutrition on the given master widget and return the canvas object."""
    nutrients = ["calories", "carbs", "fat", "protein"]
    values = []
    for n in nutrients:
        val = nutrition.get(n, "0")
        # extract numeric portion
        num = 0.0
        try:
            num = float(''.join(ch for ch in val if (ch.isdigit() or ch == '.')))
        except Exception:
            pass
        values.append(num)

    fig = Figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    bars = ax.bar(nutrients, values, color=["orange", "blue", "green", "red"])
    ax.set_title("Nutrition (approx)")
    ax.set_ylabel("Amount")
    # annotate each bar with its numeric value
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, val, f"{val}",
                ha='center', va='bottom', fontsize=8)

    canvas = FigureCanvasTkAgg(fig, master=master or root)
    canvas.draw()
    widget = canvas.get_tk_widget()
    widget.pack(pady=10)
    return canvas


def strip_html(text):
    import re
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    return clean


def show_graph_window():
    """Open a new window displaying the nutrition bar chart."""
    global last_nutrition
    if not last_nutrition:
        messagebox.showinfo("No data", "Select a recipe first to view its graph.")
        return
    # create top-level window
    win = tk.Toplevel(root)
    win.title("Nutrition Graph")
    fig = Figure(figsize=(4,3))
    ax = fig.add_subplot(111)
    nutrients = ["calories","carbs","fat","protein"]
    values = []
    for n in nutrients:
        val = last_nutrition.get(n, "0")
        num = 0.0
        try:
            num = float(''.join(ch for ch in val if (ch.isdigit() or ch == '.')))
        except Exception:
            pass
        values.append(num)
    ax.bar(nutrients, values, color=["orange","blue","green","red"])
    ax.set_title("Nutrition")
    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas.draw()
    canvas.get_tk_widget().pack()



# --- login and navigation helpers ------------------------------------------

def show_search_page():
    global search_frame, details_frame
    if details_frame:
        details_frame.pack_forget()
    if search_frame:
        search_frame.pack(fill="both", expand=True)


def show_details_page():
    global search_frame, details_frame
    if search_frame:
        search_frame.pack_forget()
    if details_frame:
        details_frame.pack(fill="both", expand=True)


def show_nutrition_only():
    """Hide detailed description canvas and display nutrition chart/table."""
    global details_canvas, nutrition_content, last_nutrition
    if details_canvas:
        details_canvas.pack_forget()
    # populate nutrition_content
    for w in nutrition_content.winfo_children():
        w.destroy()
    # chart
    # flash accent background briefly to indicate update
    nutrition_content.configure(bg=THEME['accent'])
    root.after(150, lambda: nutrition_content.configure(bg=THEME['bg']))
    plot_nutrition(last_nutrition, master=nutrition_content)
    # nutrition table using pandas for formatting
    df = pd.DataFrame([last_nutrition])[['calories','carbs','fat','protein']]
    df = df.transpose().reset_index()
    df.columns = ['nutrient','amount']
    # split unit
    df['unit'] = df['amount'].str.replace(r'[0-9\.]+','', regex=True)
    df['amount'] = df['amount'].str.replace(r'[^0-9\.]','', regex=True)
    tbl = ttk.Treeview(nutrition_content, columns=("nutrient","amount","unit"), show='headings')
    tbl.heading("nutrient", text="Nutrient")
    tbl.heading("amount", text="Amount")
    tbl.heading("unit", text="Unit")
    for _, row in df.iterrows():
        tbl.insert('', tk.END, values=(row['nutrient'].capitalize(), row['amount'], row['unit']))
    tbl.pack(fill='x', padx=10, pady=5)
    # back to details button
    tk.Button(nutrition_content, text="Show Details", command=show_details_section).pack(pady=10)
    nutrition_content.pack(fill='both', expand=True)


def show_details_section():
    """Return from nutrition view to full details."""
    global details_canvas
    if nutrition_content:
        nutrition_content.pack_forget()
    if details_canvas:
        details_canvas.pack(fill='both', expand=True)


def validate_login(username, password):
    # very basic check; could be extended.
    return bool(username and password)


def validate_login(username, password):
    # ---------- EMAIL VALIDATION ----------
    email_pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    if not re.match(email_pattern, username):
        return False, "Enter a valid email"

    # ---------- PASSWORD VALIDATION ----------
    if len(password) < 6:
        return False, "Password must be at least 6 characters"

    if not re.search(r"[A-Z]", password):
        return False, "Password must contain 1 uppercase letter"

    if not re.search(r"[a-z]", password):
        return False, "Password must contain 1 lowercase letter"

    if not re.search(r"\d", password):
        return False, "Password must contain 1 number"

    return True, ""
def attempt_login():
    user = username_entry.get().strip()
    pwd = password_entry.get().strip()

    valid, message = validate_login(user, pwd)

    if not valid:
        login_error_label.config(text=message)
        return

    # clear fields after success
    username_entry.delete(0, tk.END)
    password_entry.delete(0, tk.END)

    login_frame.pack_forget()
    build_main_ui()
    show_search_page()


def t_login():
    user = username_entry.get().strip()
    pwd = password_entry.get().strip()
    # clear entry fields regardless of success
    username_entry.delete(0, tk.END)
    password_entry.delete(0, tk.END)
    if validate_login(user, pwd):
        # hide login and prepare main interface
        login_frame.pack_forget()
        build_main_ui()
        show_search_page()
    else:
        # show styled error
        login_error_label.config(text="Invalid email or password")


def create_login_frame():
    global login_frame, username_entry, password_entry, login_error_label
    # overall frame with soft background
    login_frame = tk.Frame(root, bg=THEME['bg'])
    login_frame.pack(fill=tk.BOTH, expand=True)

    # configure ttk styles for modern look
    style = ttk.Style(root)
    style.configure('Card.TFrame', background='white', relief='flat', borderwidth=1)
    style.configure('Title.TLabel', font=('Helvetica', 20, 'bold'), background='white', foreground=THEME['accent'])
    style.configure('SubTitle.TLabel', font=('Helvetica', 12), background='white', foreground=THEME['fg'])
    style.configure('Placeholder.TEntry', foreground='#aaa', padding=5)
    style.map('Rounded.TButton', background=[('!active', THEME['accent']), ('active', '#2980b9')], foreground=[('!disabled', 'white')])

    # card frame centered
    card = ttk.Frame(login_frame, style='Card.TFrame')
    card.place(relx=0.5, rely=0.5, anchor='c', width=350, height=320)
    # title + subtitle
    ttk.Label(card, text="Recipe Finder", style='Title.TLabel').pack(pady=(20,5))
    ttk.Label(card, text="Welcome back! Please login.", style='SubTitle.TLabel').pack(pady=(0,15))

    # email entry with placeholder
    username_entry = ttk.Entry(card, width=30, style='Placeholder.TEntry')
    username_entry.insert(0, 'Email')
    username_entry.bind('<FocusIn>', lambda e: _clear_placeholder(e, 'Email'))
    username_entry.bind('<FocusOut>', lambda e: _restore_placeholder(e, 'Email'))
    username_entry.pack(pady=5)

    # password entry with placeholder and toggle
    password_entry = ttk.Entry(card, width=30, style='Placeholder.TEntry')
    password_entry.insert(0, 'Password')
    password_entry.bind('<FocusIn>', lambda e: _clear_placeholder(e, 'Password', is_password=True))
    password_entry.bind('<FocusOut>', lambda e: _restore_placeholder(e, 'Password', is_password=True))
    password_entry.pack(pady=5)
    show_var = tk.BooleanVar(value=False)
    def toggle_pw():
        password_entry.config(show='' if show_var.get() else '*')
    ttk.Checkbutton(card, text='Show password', variable=show_var, command=toggle_pw).pack(pady=(0,10))

    # error label
    login_error_label = ttk.Label(card, text="", foreground='red', background='white', font=THEME['font_small'])
    login_error_label.pack(pady=5)

    # login button
    login_btn = tk.Button(card,text="Login",bg=THEME['accent'],fg="white",font=THEME['font_medium'],relief="flat",cursor="hand2",command=attempt_login)

    login_btn.pack(pady=20, fill='x', padx=20, ipady=8)


    # helper functions for placeholder
    def _clear_placeholder(event, placeholder, is_password=False):
        if event.widget.get() == placeholder:
            event.widget.delete(0, tk.END)
            event.widget.config(foreground=THEME['fg'])
            if is_password and not show_var.get():
                event.widget.config(show='*')
    def _restore_placeholder(event, placeholder, is_password=False):
        if not event.widget.get():
            event.widget.insert(0, placeholder)
            event.widget.config(foreground='#aaa')
            event.widget.config(show='')


def build_main_ui():
    """Construct the main application frames (search and details)."""
    global entry, button, diet_var
    global search_frame, results_container, details_frame
    global details_content, nutrition_content, back_button, details_canvas

    # search frame
    search_frame = tk.Frame(root)
    # search controls
    top = tk.Frame(search_frame, bg=THEME['bg'])
    tk.Label(top, text="🔎 Ingredients:", font=THEME['font_large'], bg=THEME['bg'], fg=THEME['fg']).pack(side='left', padx=5)
    entry = tk.Entry(top, width=40)
    entry.pack(side='left', padx=5)
    # dietary filters
    diet_var = tk.StringVar(value="None")
    diets = ["None", "Vegetarian", "Vegan", "Gluten Free", "Dairy Free"]
    style = ttk.Style()
    style.configure('TMenubutton', font=THEME['font_small'])
    ttk.OptionMenu(top, diet_var, *diets).pack(side='left', padx=5)
    button = tk.Button(top, text="🔍 Search", bg=THEME['accent'], fg='white', command=search)
    button.pack(side='left', padx=5)
    top.pack(pady=10, fill='x')

    # results area (scrollable)
    results_canvas = tk.Canvas(search_frame)
    vsb = tk.Scrollbar(search_frame, orient="vertical", command=results_canvas.yview)
    results_canvas.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")
    results_canvas.pack(side="left", fill="both", expand=True)

    results_container = tk.Frame(results_canvas)
    results_canvas.create_window((0, 0), window=results_container, anchor="nw")
    def on_configure(event):
        results_canvas.configure(scrollregion=results_canvas.bbox("all"))
    results_container.bind("<Configure>", on_configure)

    # details frame (initially hidden) with scrolling
    details_frame = tk.Frame(root)
    back_button = tk.Button(details_frame, text="← Back", command=show_search_page)
    back_button.pack(anchor='w', pady=5, padx=5)
    # scrollable area for content
    details_canvas = tk.Canvas(details_frame)
    details_vsb = tk.Scrollbar(details_frame, orient="vertical", command=details_canvas.yview)
    details_canvas.configure(yscrollcommand=details_vsb.set)
    details_vsb.pack(side="right", fill="y")
    details_canvas.pack(side="left", fill="both", expand=True)
    details_content = tk.Frame(details_canvas)
    details_canvas.create_window((0,0), window=details_content, anchor="nw")
    def on_det_config(e):
        details_canvas.configure(scrollregion=details_canvas.bbox("all"))
    details_content.bind("<Configure>", on_det_config)
    nutrition_content = tk.Frame(details_frame)

    # keep the geometry size constant
    root.geometry("600x750")


def create_gui():
    global root
    root = tk.Tk()
    root.title("Recipe Finder")
    root.geometry("600x750")

    # apply theme styles
    style = ttk.Style(root)
    style.configure('TFrame', background=THEME['bg'])
    style.configure('TLabel', background=THEME['bg'], foreground=THEME['fg'], font=THEME['font_medium'])
    style.configure('TButton', font=THEME['font_small'])

    create_login_frame()
    root.mainloop()


if __name__ == "__main__":
    create_gui()
