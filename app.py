import streamlit as st
import os
import bcrypt
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image
from google import genai 
from supabase import create_client, Client
from streamlit_cookie_manager import CookieManager # إضافة إدارة الكوكيز

# =========================================================================
# I. التهيئة الأساسية والثوابت (Supabase, Gemini, Cookies)
# =========================================================================

# (نستخدم load_dotenv لقراءة المتغيرات محليًا، وتعتمد على st.secrets عند النشر)
load_dotenv() 

MAX_QUESTIONS_DAILY = 5

# --- إعداد الكوكيز ---
# مفاتيح خاصة بالكوكيز - يرجى عدم تغييرها بعد النشر
COOKIE_KEY_USER = "user_email_cookie" 
COOKIE_KEY_LOGGED_IN = "logged_in_cookie"

# إعداد الروابط الخاصة بك (لتحديثها لاحقاً)
YOUTUBE_LINK = "https://www.youtube.com/user/YourChannelName" 
PROJECT_LINK = "https://YourAwesomeProject.com" 

# تهيئة مدير ملفات تعريف الارتباط
cookie_manager = CookieManager()

# --- تهيئة الاتصال بـ Gemini و Supabase ---
try:
    # 1. جلب المفاتيح من st.secrets (أو os.getenv محليًا)
    API_KEY = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))
    SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL"))
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.getenv("SUPABASE_KEY"))

    if not API_KEY or not SUPABASE_URL or not SUPABASE_KEY:
        st.error("الرجاء التأكد من إعداد جميع المفاتيح (GEMINI_API_KEY, SUPABASE_URL, SUPABASE_KEY) في ملف الأسرار.")
        st.stop()
        
    client = genai.Client(api_key=API_KEY) 

    @st.cache_resource
    def init_supabase_client(url, key):
        """تهيئة عميل Supabase وتخزينه مؤقتاً."""
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
    st.error("لم يتم العثور على ملف system_prompt.txt. تأكد من وجوده في نفس المجلد.")
    st.stop()
    
st.set_page_config(page_title="Math AI with zaoujal", layout="centered")

# =========================================================================
# II. دوال Supabase وإدارة المستخدمين
# =========================================================================

@st.cache_data(ttl=60) # نستخدم التخزين المؤقت للحد من استدعاءات API
def get_user_data(email):
    """جلب بيانات المستخدم من Supabase."""
    try:
        # ملاحظة: يجب أن يتطابق 'email' مع المفتاح الأساسي أو أن يكون مفهرساً
        response = supabase.table("users").select("*").eq("email", email).single().execute()
        return response.data 
    except Exception:
        return None 

def add_user(email, password, grade):
    """إضافة مستخدم جديد إلى Supabase."""
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    try:
        data = {
            "email": email,
            "password_hash": hashed_password,
            "school_grade": grade,
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

def update_user_usage(email, increment=False):
    """تحديث عدد استخدامات المستخدم وإعادة تعيينها يومياً."""
    user_data = get_user_data(email)
    today_str = datetime.now().strftime("%Y-%m-%d")

    if user_data is None: 
        return False, 0
    
    current_used = user_data.get('questions_used', 0)
    last_date_str = user_data.get('last_use_date', today_str)
    is_premium = user_data.get('is_premium', False)

    # منطق المستخدم المميز (Premium): لا يوجد تقييد
    if is_premium:
        return True, 0 

    # منطق المستخدم العادي (Free)
    if last_date_str != today_str:
        current_used = 0
    
    new_used = current_used
    can_use = True
    
    if increment and current_used < MAX_QUESTIONS_DAILY:
        new_used = current_used + 1
        
        # تحديث Supabase
        supabase.table("users").update({
            "questions_used": new_used, 
            "last_use_date": today_str
        }).eq("email", email).execute()
        
        get_user_data.clear() 
    
    elif increment and current_used >= MAX_QUESTIONS_DAILY:
        can_use = False

    return can_use, new_used

# =========================================================================
# III. دوال تسجيل الدخول/الخروج وتذكّر المستخدم (Cookies)
# =========================================================================

def initialize_session_state_with_cookies():
    """يهيئ حالة الجلسة عند بدء تشغيل التطبيق بناءً على الكوكي المحفوظ."""
    # نستخدم مفتاح مختلف لمنع التداخل مع حالة المستخدم الافتراضية
    if 'initialized_cookies_done' not in st.session_state:
        user_from_cookie = cookie_manager.get(COOKIE_KEY_USER)
        
        if user_from_cookie:
            # التحقق مرة أخرى من وجود المستخدم في Supabase (لضمان أن الحساب لم يُحذف)
            user_data = get_user_data(user_from_cookie)
            if user_data:
                # تحديث حالة الجلسة بما يتوافق مع بيانات Supabase
                st.session_state['logged_in'] = True
                st.session_state['user_email'] = user_from_cookie
                st.session_state['is_admin'] = user_data.get('is_admin', False) 
                st.session_state['is_premium'] = user_data.get('is_premium', False) 
                st.session_state['initialized_cookies_done'] = True
                return

        # إذا لم يتم العثور على كوكي أو المستخدم غير صالح
        st.session_state['logged_in'] = False
        st.session_state['user_email'] = None
        st.session_state['is_admin'] = False
        st.session_state['is_premium'] = False
        st.session_state['initialized_cookies_done'] = True
        
    # يجب استدعاء هذا الأمر دائماً لحفظ التغييرات
    cookie_manager.save()
    
# Call the new initializer before the main execution
initialize_session_state_with_cookies()

def logout_user():
    """تسجيل الخروج مع حذف الكوكيز وتحديث حالة الجلسة."""
    # حذف حالة الجلسة
    st.session_state['logged_in'] = False
    st.session_state['user_email'] = None
    st.session_state['is_admin'] = False
    st.session_state['is_premium'] = False
    
    # حذف الكوكي
    cookie_manager.delete(COOKIE_KEY_USER)
    cookie_manager.save()
    st.info("تم تسجيل الخروج بنجاح.")
    st.rerun()

# =========================================================================
# IV. دوال عرض نماذج التسجيل والدخول
# =========================================================================

def login_form():
    """عرض نموذج تسجيل الدخول."""
    with st.form("login_form"):
        st.subheader("تسجيل الدخول")
        email = st.text_input("البريد الإلكتروني").strip()
        password = st.text_input("كلمة المرور", type="password")
        submitted = st.form_submit_button("تسجيل الدخول")

        if submitted:
            user_data = get_user_data(email) 
            
            if user_data and bcrypt.checkpw(password.encode('utf-8'), user_data.get('password_hash', '').encode('utf-8')): 
                
                # تحديث حالة الجلسة
                st.session_state['logged_in'] = True
                st.session_state['user_email'] = email
                st.session_state['is_admin'] = user_data.get('is_admin', False) 
                st.session_state['is_premium'] = user_data.get('is_premium', False) 
                
                # *** ميزة تذكّر المستخدم (الكوكيز) ***
                cookie_manager.set(COOKIE_KEY_USER, email, expires_at=None)
                cookie_manager.save()
                
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
        
        # قائمة المستويات التعليمية المغربية المحدثة
        grades = [
            "السنة الأولى إعدادي",
            "السنة الثانية إعدادي",
            "السنة الثالثة إعدادي",
            "الجذع المشترك العلمي",
            "الأولى بكالوريا (علوم تجريبية)",
            "الأولى بكالوريا (علوم رياضية)",
            "الثانية بكالوريا (علوم فيزيائية)",
            "الثانية بكالوريا (علوم الحياة والأرض)",
            "الثانية بكالوريا (علوم رياضية)",
            "غير ذلك (جامعة/آداب/تكوين مهني)"
        ]
        
        # استخدام بياناتك الشخصية يا أحمد كافتراضي
        initial_grade_index = grades.index("الثانية بكالوريا (علوم رياضية)") if "الثانية بكالوريا (علوم رياضية)" in grades else 0
        grade = st.selectbox("المستوى الدراسي (النظام المغربي)", grades, index=initial_grade_index)
        
        submitted = st.form_submit_button("تسجيل الحساب")

        if submitted:
            if not email or not password or len(password) < 6:
                st.error("الرجاء إدخال بيانات صالحة وكلمة مرور لا تقل عن 6 أحرف.")
                return

            if add_user(email, password, grade):
                st.success("تم التسجيل بنجاح! يمكنك الآن تسجيل الدخول.")
            else:
                st.error("البريد الإلكتروني مُسجل بالفعل. حاول تسجيل الدخول.")

# =========================================================================
# V. دالة لوحة التحكم الإدارية (Admin Dashboard) 👑
# =========================================================================

def admin_dashboard_ui():
    """عرض لوحة التحكم للمسؤولين فقط لإدارة صلاحيات المستخدمين المميزين."""
    st.title("لوحة التحكم الإدارية 👑")
    st.caption("هذه الصفحة متاحة لك بصفتك مسؤول المشروع.")

    try:
        response = supabase.table("users").select("*").order("email").execute()
        users = response.data

        st.subheader("إدارة الوصول المميز")
        
        # إنشاء إطار بيانات (DataFrame) قابل للتعديل
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
                    # تحديث Supabase
                    supabase.table("users").update({
                        "is_premium": row['is_premium']
                    }).eq("email", row['email']).execute()
            
            st.success("تم تحديث صلاحيات الوصول بنجاح!")
            get_user_data.clear() 
            st.rerun()

    except Exception as e:
        st.error(f"خطأ في جلب بيانات لوحة التحكم. تأكد من إعداد سياسات الأمان (RLS) للسماح للمسؤولين بالقراءة والتحديث: {e}")


# =========================================================================
# VI. دالة واجهة التطبيق الرئيسية (Main UI) مع البث (Streaming)
# =========================================================================

def main_app_ui():
    """عرض واجهة التطبيق الرئيسية (حل المسائل) والتحكم بالتقييد والتخصيص."""
    
    st.title("🇲🇦 حلول المسائل بالذكاء الاصطناعي")
    st.caption("يرجى التأكد من تحميل صورة عالية الجودة مع نص واضح وتمرين واحد")
    
    is_premium = st.session_state.get('is_premium', False)
    user_email = st.session_state['user_email']

    # 1. تحديث العداد وعرض حالة الاستخدام
    if not is_premium:
        can_use, current_used = update_user_usage(user_email)
        
        st.info(f"الأسئلة المجانية اليومية المتبقية: {MAX_QUESTIONS_DAILY - current_used} من {MAX_QUESTIONS_DAILY}.")
        
        if current_used >= MAX_QUESTIONS_DAILY:
            st.error(f"لقد استنفدت الحد الأقصى ({MAX_QUESTIONS_DAILY}) من الأسئلة لهذا اليوم. يرجى العودة غداً. (هنا يمكنك إضافة رابط الاشتراك المدفوع).")
            st.stop()
    else:
        st.info("✅ لديك وصول مميز (Premium Access) وغير محدود!")


    # 2. منطق رفع الصورة والحل
    uploaded_file = st.file_uploader("قم بتحميل صورة المسألة", type=["png", "jpg", "jpeg"])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption='صورة المسألة.', use_column_width=True)
        
        if st.button("🚀 ابدأ الحل والتحليل"):
            
            # استخدام st.status لتقليل الإحساس بالانتظار وتوفير مكان للتدفق
            with st.status("جاري تحليل الصورة وتقديم الحل... (الرد يظهر بالتدفق السريع)", expanded=True) as status:
                
                try:
                    
                    # 🌟 التعديل الحاسم: تخصيص الحل حسب المستوى 🌟
                    full_user_data = get_user_data(user_email)
                    user_grade = full_user_data.get('school_grade', "مستوى غير محدد")
                    
                    # إنشاء تعليمات النظام المخصصة
                    custom_prompt = (
                        f"{SYSTEM_PROMPT}\n"
                        f"مستوى الطالب هو: {user_grade}. يجب أن يكون الحل المفصل المقدم مناسبًا تمامًا لهذا المستوى التعليمي المحدد في النظام المغربي، مع التركيز على المنهجيات التي تدرس في هذا المستوى."
                    )
                    
                    # تجميع المحتوى: التعليمات المخصصة + الصورة
                    contents = [custom_prompt, image]
                    # -------------------- 🌟 نهاية التخصيص 🌟 --------------------

                    # 1. استدعاء Gemini في وضع البث (Streaming)
                    stream = client.models.generate_content_stream(
                        model='gemini-2.5-flash', 
                        contents=contents
                    )
                    
                    # 2. عرض الرد مباشرة عبر st.write_stream
                    st.subheader("📝 الحل المفصل (يتم عرضه فورياً)")
                    # استخدم مكان الـ status نفسه لعرض التدفق
                    st.write_stream(stream)
                    
                    # 3. تحديث الاستخدام بعد نجاح الحل (فقط للمستخدمين العاديين)
                    if not is_premium:
                        update_user_usage(user_email, increment=True) 
                    
                    # 4. تحديث حالة الـ status
                    status.update(label="تم تحليل وحل المسألة بنجاح! 🎉", state="complete", expanded=False)
                    
                except Exception as e:
                    status.update(label="فشل التحليل", state="error", expanded=True)
                    st.error(f"حدث خطأ أثناء الاتصال بالنموذج. تأكد من جودة الصورة: {e}")
                    
# =========================================================================
# VII. المنطق الرئيسي للتطبيق (Main)
# =========================================================================

# الشريط الجانبي (Side Bar)
with st.sidebar:
    st.image("https://placehold.co/100x100/30A4D5/ffffff?text=AI", use_column_width=False)
    st.title("Math AI zaoujal 🧠")
    st.markdown("---")
    
    # عرض معلومات المستخدم وزر الخروج
    if st.session_state['logged_in']:
        st.success(f"مرحباً بك: {st.session_state['user_email']}")
        st.caption(f"المستوى: {get_user_data(st.session_state['user_email']).get('school_grade', 'غير محدد')}")
        if st.button("🚪 تسجيل الخروج", use_container_width=True, key="logout_btn"):
            logout_user() # استخدام دالة تسجيل الخروج الجديدة
    
    # منطقة الروابط (لتحديثها غداً)
    st.markdown("---")
    st.header("تابعوني")
    st.markdown(f"**🎬 قناتي على يوتيوب:** [اشترك الآن]({YOUTUBE_LINK})")
    st.markdown(f"**🔗 مشروعي الإلكتروني:** [المزيد هنا]({PROJECT_LINK})")


if st.session_state['logged_in']:
    is_admin = st.session_state.get('is_admin', False)

    if is_admin:
        # إذا كان مسؤولاً، يظهر له تبويب الإدارة
        admin_tab, app_tab = st.tabs(["لوحة التحكم (Admin)", "حل المسائل"])
        with admin_tab:
            admin_dashboard_ui() 
        with app_tab:
            main_app_ui()
    else:
        # المستخدم العادي يرى التطبيق فقط
        main_app_ui()
else:
    st.header("أهلاً بك في منصة Math AI zaoujal")
    st.subheader(f"الرجاء تسجيل الدخول أو إنشاء حساب لاستخدام خدمة حل المسائل ({MAX_QUESTIONS_DAILY} أسئلة مجانية يومياً)")
    login_tab, register_tab = st.tabs(["تسجيل الدخول", "إنشاء حساب"])
    
    with login_tab:
        login_form()
    
    with register_tab:
        register_form()

# ملاحظة هامة: تم مسح جزء التهيئة القديم ليحل محله initialize_session_state_with_cookies()
