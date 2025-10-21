import streamlit as st
import os
import bcrypt
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image
from google import genai 
from supabase import create_client, Client
import io 

# -------------------- 1. الثوابت والإعداد الأولي --------------------

load_dotenv() 

MAX_QUESTIONS_DAILY = 5

# تهيئة الاتصال بـ Gemini و Supabase
try:
    API_KEY = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
    SUPABASE_URL = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")

    if not API_KEY or not SUPABASE_URL or not SUPABASE_KEY:
        st.error("الرجاء التأكد من إعداد جميع المفاتيح. توقف التطبيق.")
        st.stop()
        
    client = genai.Client(api_key=API_KEY) 

    @st.cache_resource
    def init_supabase_client(url, key):
        return create_client(url, key)
    
    supabase: Client = init_supabase_client(SUPABASE_URL, SUPABASE_KEY)

except Exception as e:
    st.error(f"حدث خطأ في تهيئة الاتصال: {e}")
    st.stop()


# 2. قراءة تعليمات النظام من ملف system_prompt.txt
try:
    with open("system_prompt.txt", "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()
except FileNotFoundError:
    st.error("لم يتم العثور على ملف system_prompt.txt. توقف التطبيق.")
    st.stop()
    
st.set_page_config(page_title="Math AI with zaoujal", layout="centered")

# -------------------- 3. دوال Supabase وإدارة المستخدمين --------------------

@st.cache_data(ttl=60) 
def get_user_data(email):
    """جلب بيانات المستخدم من Supabase."""
    try:
        # جلب البيانات دون كلمة المرور المشفرة لتقليل الكاش (يمكن جلبها عند الحاجة فقط)
        response = supabase.table("users").select("*").eq("email", email).single().execute()
        return response.data
    except Exception:
        return None

# 🌟 دالة جديدة: تحديث كلمة المرور فقط 🌟
def update_user_password(email, new_password):
    """تحديث كلمة المرور المشفرة للمستخدم في Supabase."""
    try:
        if len(new_password) < 6:
            return False
            
        # تشفير كلمة المرور الجديدة
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        supabase.table("users").update({
            "password_hash": hashed_password
        }).eq("email", email).execute()
        
        # لا حاجة لمسح الكاش هنا، فقط عند تغيير التفضيلات أو التسجيل
        return True
    except Exception as e:
        st.error(f"خطأ في تحديث كلمة المرور: {e}")
        return False
# ------------------------------------------------------------------------

def add_user(email, password, grade, language, answer_style):
    """إضافة مستخدم جديد إلى Supabase مع تفضيلاته."""
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    try:
        data = {
            "email": email,
            "password_hash": hashed_password,
            "school_grade": grade,
            "preferred_language": language, 
            "answer_style": answer_style,
            "last_use_date": datetime.now().strftime("%Y-%m-%d"),
            "questions_used": 0,
            "is_admin": False, 
            "is_premium": False 
        }
        supabase.table("users").insert(data).execute()
        get_user_data.clear() 
        return True
    except Exception:
        return False

def update_user_preferences(email, grade, language, answer_style):
    """تحديث المستوى الدراسي واللغة وطريقة الحل في Supabase."""
    try:
        supabase.table("users").update({
            "school_grade": grade,
            "preferred_language": language,
            "answer_style": answer_style
        }).eq("email", email).execute()
        get_user_data.clear() 
        return True
    except Exception as e:
        st.error(f"خطأ في تحديث التفضيلات: {e}")
        return False

def update_user_usage(email, increment=False):
    """تحديث عدد استخدامات المستخدم وإعادة تعيينها يومياً."""
    user_data = get_user_data(email)
    today_str = datetime.now().strftime("%Y-%m-%d")

    if user_data is None: 
        return False, 0
    
    current_used = user_data.get('questions_used', 0)
    last_date_str = user_data.get('last_use_date', today_str)
    is_premium = user_data.get('is_premium', False)

    if is_premium:
        return True, 0 

    if last_date_str != today_str:
        current_used = 0
    
    new_used = current_used
    can_use = True
    
    if increment and current_used < MAX_QUESTIONS_DAILY:
        new_used = current_used + 1
        
        supabase.table("users").update({
            "questions_used": new_used, 
            "last_use_date": today_str
        }).eq("email", email).execute()
        
        get_user_data.clear() 
    
    elif increment and current_used >= MAX_QUESTIONS_DAILY:
        can_use = False

    return can_use, new_used


# -------------------- 4. دوال عرض نماذج التسجيل والدخول (كما هي) --------------------

def login_form():
    """عرض نموذج تسجيل الدخول."""
    with st.form("login_form"):
        st.subheader("تسجيل الدخول")
        email = st.text_input("البريد الإلكتروني").strip()
        password = st.text_input("كلمة المرور", type="password")
        submitted = st.form_submit_button("تسجيل الدخول")

        if submitted:
            user_data = get_user_data(email) 
            
            # ملاحظة: دالة get_user_data لا تجلب كلمة المرور المشفرة افتراضياً،
            # يجب أن يتم جلبها هنا تحديداً لعمل checkpw
            try:
                # جلب البيانات مع كلمة المرور المشفرة لغرض التحقق فقط
                response = supabase.table("users").select("password_hash").eq("email", email).single().execute()
                password_hash = response.data.get('password_hash', '')
            except Exception:
                password_hash = ''
            
            if user_data and bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')): 
                st.session_state['logged_in'] = True
                st.session_state['user_email'] = email
                st.session_state['is_admin'] = user_data.get('is_admin', False) 
                st.session_state['is_premium'] = user_data.get('is_premium', False) 

                st.success("تم تسجيل الدخول بنجاح! 🥳")
                st.rerun()
            else:
                st.error("خطأ في البريد الإلكتروني أو كلمة المرور.")

def register_form():
    """عرض نموذج تسجيل حساب جديد."""
    with st.form("register_form"):
        st.subheader("إنشاء حساب جديد")
        email = st.text_input("البريد الإلكتروني").strip()
        password = st.text_input("كلمة المرور", type="password")
        
        grades = [
            "السنة الأولى إعدادي", "السنة الثانية إعدادي", "السنة الثالثة إعدادي",
            "الجذع المشترك العلمي",
            "الأولى بكالوريا (علوم تجريبية)", "الأولى بكالوريا (علوم رياضية)",
            "الثانية بكالوريا (علوم فيزيائية)", "الثانية بكالوريا (علوم الحياة والأرض)",
            "الثانية بكالوريا (علوم رياضية)", 
            "غير ذلك (جامعة/آداب/تكوين مهني)"
        ]
        
        initial_grade_index = grades.index("الثانية بكالوريا (علوم رياضية)") if "الثانية بكالوريا (علوم رياضية)" in grades else 0
        grade = st.selectbox("المستوى الدراسي (النظام المغربي)", grades, index=initial_grade_index)
        
        language = st.radio(
            "اللغة المفضلة للحل",
            ["العربية (Arabe)", "الفرنسية (Français)"],
            index=0 
        )
        
        answer_style = st.selectbox(
            "طريقة تقديم الحل",
            [
                "الحل مع شرح مفصل وتوضيحات (Explication Détaillée)",
                "الحل في خطوات منظمة وواضحة (Étapes Claires)",
                "النتيجة النهائية والحل المباشر (Réponse Directe)"
            ],
            index=0 
        )
        
        submitted = st.form_submit_button("تسجيل الحساب")

        if submitted:
            if not email or not password or len(password) < 6:
                st.error("الرجاء إدخال بيانات صالحة وكلمة مرور لا تقل عن 6 أحرف.")
                return

            if add_user(email, password, grade, language, answer_style):
                st.success("تم التسجيل بنجاح! يمكنك الآن تسجيل الدخول.")
            else:
                st.error("البريد الإلكتروني مُسجل بالفعل. حاول تسجيل الدخول.")

# -------------------- 5. لوحة التحكم الإدارية (Admin Dashboard) (كما هي) --------------------

def admin_dashboard_ui():
    """عرض لوحة التحكم للمسؤولين فقط لإدارة صلاحيات المستخدمين المميزين."""
    st.title("لوحة التحكم الإدارية 👑")
    st.caption("هذه الصفحة متاحة لك بصفتك مسؤول المشروع.")

    try:
        response = supabase.table("users").select("*").order("email").execute()
        users = response.data

        st.subheader("إدارة الوصول المميز")
        
        users_df = pd.DataFrame(users)
        
        edited_df = st.data_editor(
            users_df[['email', 'school_grade', 'is_premium']],
            column_config={
                "is_premium": st.column_config.CheckboxColumn(
                    "وصول مميز (Premium)",
                    help="تفعيل الوصول غير المحدود لهذا المستخدم.",
                    default=False
                )
            },
            hide_index=True,
            num_rows="fixed"
        )
        
        if st.button("🚀 تحديث صلاحيات الوصول"):
            for index, row in edited_df.iterrows():
                original_row = users_df[users_df['email'] == row['email']].iloc[0]
                
                if original_row['is_premium'] != row['is_premium']:
                    supabase.table("users").update({
                        "is_premium": row['is_premium']
                    }).eq("email", row['email']).execute()
            
            st.success("تم تحديث صلاحيات الوصول بنجاح!")
            get_user_data.clear() 
            st.rerun()

    except Exception as e:
        st.error(f"خطأ في جلب بيانات لوحة التحكم: {e}")


# -------------------- 6. دالة الإعدادات (Settings Modal) ⚙️ --------------------

def settings_modal(user_email):
    """عرض نموذج يسمح للمستخدم بتغيير تفضيلاته وكلمة المرور."""
    
    user_data = get_user_data(user_email)
    
    # تعريف القوائم المشتركة
    grades = [
        "السنة الأولى إعدادي", "السنة الثانية إعدادي", "السنة الثالثة إعدادي",
        "الجذع المشترك العلمي",
        "الأولى بكالوريا (علوم تجريبية)", "الأولى بكالوريا (علوم رياضية)",
        "الثانية بكالوريا (علوم فيزيائية)", "الثانية بكالوريا (علوم الحياة والأرض)",
        "الثانية بكالوريا (علوم رياضية)", 
        "غير ذلك (جامعة/آداب/تكوين مهني)"
    ]
    languages = ["العربية (Arabe)", "الفرنسية (Français)"]
    answer_styles = [
        "الحل مع شرح مفصل وتوضيحات (Explication Détaillée)",
        "الحل في خطوات منظمة وواضحة (Étapes Claires)",
        "النتيجة النهائية والحل المباشر (Réponse Directe)"
    ]

    current_grade = user_data.get('school_grade')
    current_lang = user_data.get('preferred_language')
    current_style = user_data.get('answer_style')
    
    try:
        grade_index = grades.index(current_grade) if current_grade in grades else 0
        lang_index = languages.index(current_lang) if current_lang in languages else 0
        style_index = answer_styles.index(current_style) if current_style in answer_styles else 0
    except:
        grade_index, lang_index, style_index = 0, 0, 0 

    # 1. نموذج تحديث التفضيلات (لغة ومستوى ونمط)
    with st.form("preferences_form"):
        st.subheader("⚙️ تفضيلات الحل")
        
        new_grade = st.selectbox("المستوى الدراسي", grades, index=grade_index)
        new_lang = st.radio("اللغة المفضلة للحل", languages, index=lang_index)
        new_style = st.selectbox("طريقة تقديم الحل", answer_styles, index=style_index)
        
        submitted_pref = st.form_submit_button("حفظ التفضيلات")

        if submitted_pref:
            if update_user_preferences(user_email, new_grade, new_lang, new_style):
                st.success("تم حفظ تفضيلاتك بنجاح! 🎉")
                st.rerun()
            else:
                st.error("فشل حفظ التفضيلات. حاول مجدداً.")

    st.markdown("---")
    
    # 2. نموذج تغيير كلمة المرور 🔑
    with st.form("password_form"):
        st.subheader("🔐 تغيير كلمة المرور")
        
        new_password = st.text_input("كلمة المرور الجديدة", type="password")
        confirm_password = st.text_input("تأكيد كلمة المرور الجديدة", type="password")
        
        submitted_pass = st.form_submit_button("تغيير كلمة المرور")
        
        if submitted_pass:
            if new_password != confirm_password:
                st.error("كلمتا المرور غير متطابقتين.")
            elif len(new_password) < 6:
                st.error("يجب أن تكون كلمة المرور 6 أحرف على الأقل.")
            elif update_user_password(user_email, new_password):
                st.success("تم تغيير كلمة المرور بنجاح! يرجى استخدامها في المرة القادمة. 🥳")
                # لا نحتاج لـ rerun هنا لأن المستخدم يمكنه الاستمرار
            else:
                st.error("فشل تغيير كلمة المرور.")


# -------------------- 7. دالة واجهة التطبيق الرئيسية (المُعدّلة لإظهار الأيقونة) --------------------

def main_app_ui():
    """عرض واجهة التطبيق الرئيسية (حل المسائل) والتحكم بالتقييد والتخصيص."""
    
    # إضافة الأيقونة في الأعلى 
    col1, col2 = st.columns([0.8, 0.2])
    with col1:
        st.title("🇲🇦 حلول المسائل بالذكاء الاصطناعي")
    with col2:
        with st.popover("⚙️", help="تغيير إعدادات اللغة والمستوى وطريقة الحل وكلمة المرور"):
            settings_modal(st.session_state['user_email'])
    
    user_email = st.session_state['user_email']
    is_premium = st.session_state.get('is_premium', False)

    # 1. تحديث العداد وعرض حالة الاستخدام
    if not is_premium:
        can_use, current_used = update_user_usage(user_email)
        
        st.info(f"الأسئلة المجانية اليومية المتبقية: {MAX_QUESTIONS_DAILY - current_used} من {MAX_QUESTIONS_DAILY}.")
        
        if current_used >= MAX_QUESTIONS_DAILY:
            st.error(f"لقد استنفدت الحد الأقصى ({MAX_QUESTIONS_DAILY}) من الأسئلة لهذا اليوم.")
            st.stop()
    else:
        st.info("✅ لديك وصول مميز (Premium Access) وغير محدود!")


    # 2. منطق رفع الصورة والحل
    uploaded_file = st.file_uploader("قم بتحميل صورة المسألة", type=["png", "jpg", "jpeg"])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption='صورة المسألة.', use_column_width=True)
        
        if st.button("🚀 ابدأ الحل والتحليل"):
            
            if not is_premium:
                 can_use, current_used = update_user_usage(user_email)
                 if not can_use:
                     st.error(f"لقد استنفدت الحد الأقصى ({MAX_QUESTIONS_DAILY}) من الأسئلة لهذا اليوم.")
                     st.stop()
            
            with st.spinner('يتم تحليل الصورة وتقديم الحل...'):
                try:
                    
                    full_user_data = get_user_data(user_email)
                    user_grade = full_user_data.get('school_grade', "مستوى غير محدد")
                    user_lang = full_user_data.get('preferred_language', "العربية (Arabe)")
                    user_style = full_user_data.get('answer_style', "الحل مع شرح مفصل وتوضيحات (Explication Détaillée)")

                    # عرض التفضيلات للمستخدم
                    st.markdown(f"**تفضيلاتك:** المستوى: **{user_grade}** | اللغة: **{user_lang}** | النمط: **{user_style}** ⚙️") 
                    
                    # إنشاء تعليمات النظام المخصصة
                    custom_prompt = (
                        f"{SYSTEM_PROMPT}\n"
                        f"مستوى الطالب هو: {user_grade}. "
                        f"يجب أن يكون الحل المقدم **باللغة {user_lang}**. "
                        f"النمط المطلوب لتقديم الحل هو: **{user_style}**. "
                        f"الرجاء التأكد من أن الحل مناسب تمامًا لهذا المستوى ولهذه التفضيلات المحددة."
                    )
                    
                    contents = [custom_prompt, image]
                    
                    # -------------------- التدفق --------------------
                    
                    st.subheader("📝 الحل المفصل")
                    placeholder = st.empty() 
                    full_response = ""
                    
                    response_stream = client.models.generate_content_stream(
                        model='gemini-2.5-flash', 
                        contents=contents
                    )
                    
                    for chunk in response_stream:
                        full_response += chunk.text
                        placeholder.markdown(full_response + "▌") 
                        
                    placeholder.markdown(full_response)
                    st.success("تم تحليل وحل المسألة بنجاح! 🎉")
                    
                    if not is_premium:
                        update_user_usage(user_email, increment=True) 
                        
                except Exception as e:
                    st.error(f"حدث خطأ أثناء الاتصال بالنموذج: {e}")
                    
# -------------------- 8. المنطق الرئيسي للتطبيق (Main) --------------------

# تهيئة حالة الجلسة
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_email' not in st.session_state:
    st.session_state['user_email'] = None
if 'is_admin' not in st.session_state:
    st.session_state['is_admin'] = False
if 'is_premium' not in st.session_state:
    st.session_state['is_premium'] = False

if st.session_state['logged_in']:
    is_admin = st.session_state.get('is_admin', False)

    if is_admin:
        admin_tab, app_tab = st.tabs(["لوحة التحكم (Admin)", "حل المسائل"])
        with admin_tab:
            admin_dashboard_ui() 
        with app_tab:
            main_app_ui()
    else:
        main_app_ui()
else:
    st.header("أهلاً بك في منصة Math AI zaoujal")
    st.subheader(f"الرجاء تسجيل الدخول أو إنشاء حساب لاستخدام خدمة حل المسائل ({MAX_QUESTIONS_DAILY} أسئلة مجانية يومياً)")
    login_tab, register_tab = st.tabs(["تسجيل الدخول", "إنشاء حساب"])
    
    with login_tab:
        login_form()
    
    with register_tab:
        register_form()
