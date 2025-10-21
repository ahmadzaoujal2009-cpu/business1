from PIL import Image
from google import genai 
from supabase import create_client, Client
from streamlit_cookie_manager import CookieManager # إضافة إدارة الكوكيز
# إذا كنت تستخدم OpenAI، استبدل genai بـ openai

# =========================================================================
# I. التهيئة الأساسية والثوابت (Supabase, Gemini, Cookies)
# =========================================================================
# -------------------- 1. الثوابت والإعداد الأولي --------------------

# (نستخدم load_dotenv لقراءة المتغيرات محليًا، وتعتمد على st.secrets عند النشر)
load_dotenv() 

DB_FILE = 'users.db' # هذا أصبح غير مستخدم الآن، لكن نتركه للتوضيح
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
# تهيئة الاتصال بـ Gemini و Supabase
try:
    # 1. جلب المفاتيح من st.secrets (أو os.getenv محليًا)
    API_KEY = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))
@@ -45,7 +32,6 @@

    @st.cache_resource
    def init_supabase_client(url, key):
        """تهيئة عميل Supabase وتخزينه مؤقتاً."""
        return create_client(url, key)

    supabase: Client = init_supabase_client(SUPABASE_URL, SUPABASE_KEY)
@@ -65,22 +51,22 @@ def init_supabase_client(url, key):

st.set_page_config(page_title="Math AI with zaoujal", layout="centered")

# =========================================================================
# II. دوال Supabase وإدارة المستخدمين
# =========================================================================
# -------------------- 3. دوال Supabase وإدارة المستخدمين --------------------

# دوال Supabase تحل محل SQLite بالكامل

@st.cache_data(ttl=60) # نستخدم التخزين المؤقت للحد من استدعاءات API
def get_user_data(email):
    """جلب بيانات المستخدم من Supabase."""
    try:
        # ملاحظة: يجب أن يتطابق 'email' مع المفتاح الأساسي أو أن يكون مفهرساً
        response = supabase.table("users").select("*").eq("email", email).single().execute()
        return response.data 
        return response.data # البيانات تكون في خاصية .data
    except Exception:
        return None 
        return None # إذا لم يتم العثور على المستخدم

def add_user(email, password, grade):
    """إضافة مستخدم جديد إلى Supabase."""
    # تشفير كلمة المرور وتشفير الـ Hash إلى سلسلة نصية (string) لتخزينها في Supabase
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    try:
        data = {
@@ -93,6 +79,7 @@ def add_user(email, password, grade):
            "is_premium": False 
        }
        supabase.table("users").insert(data).execute()
        # مسح الكاش لضمان جلب المستخدم الجديد عند التسجيل
        get_user_data.clear() 
        return True
    except Exception:
@@ -110,11 +97,11 @@ def update_user_usage(email, increment=False):
    last_date_str = user_data.get('last_use_date', today_str)
    is_premium = user_data.get('is_premium', False)

    # منطق المستخدم المميز (Premium): لا يوجد تقييد
    # **منطق المستخدم المميز (Premium)**
    if is_premium:
        return True, 0 

    # منطق المستخدم العادي (Free)
    # **منطق المستخدم العادي (Free)**
    if last_date_str != today_str:
        current_used = 0

@@ -130,65 +117,16 @@ def update_user_usage(email, increment=False):
            "last_use_date": today_str
        }).eq("email", email).execute()

        # مسح الكاش لضمان أن العداد يظهر التحديث الفوري
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
# -------------------- 4. دوال عرض نماذج التسجيل والدخول --------------------

def login_form():
    """عرض نموذج تسجيل الدخول."""
@@ -202,24 +140,20 @@ def login_form():
            user_data = get_user_data(email) 

            if user_data and bcrypt.checkpw(password.encode('utf-8'), user_data.get('password_hash', '').encode('utf-8')): 
                
                # تحديث حالة الجلسة
                st.session_state['logged_in'] = True
                st.session_state['user_email'] = email
                # تخزين حالة المسؤول والوصول المميز
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
    # (يبقى الكود كما هو، مع استخدام دالة add_user الجديدة)
    with st.form("register_form"):
        st.subheader("إنشاء حساب جديد")
        email = st.text_input("البريد الإلكتروني").strip()
@@ -238,8 +172,7 @@ def register_form():
            "الثانية بكالوريا (علوم رياضية)",
            "غير ذلك (جامعة/آداب/تكوين مهني)"
        ]
        
        # استخدام بياناتك الشخصية يا أحمد كافتراضي
        # استخدام بياناتك الشخصية يا أحمد (الثانية بكالوريا (علوم رياضية)) كمثال
        initial_grade_index = grades.index("الثانية بكالوريا (علوم رياضية)") if "الثانية بكالوريا (علوم رياضية)" in grades else 0
        grade = st.selectbox("المستوى الدراسي (النظام المغربي)", grades, index=initial_grade_index)

@@ -255,16 +188,15 @@ def register_form():
            else:
                st.error("البريد الإلكتروني مُسجل بالفعل. حاول تسجيل الدخول.")

# =========================================================================
# V. دالة لوحة التحكم الإدارية (Admin Dashboard) 👑
# =========================================================================
# -------------------- 5. دالة لوحة التحكم الإدارية (Admin Dashboard) 👑 --------------------

def admin_dashboard_ui():
    """عرض لوحة التحكم للمسؤولين فقط لإدارة صلاحيات المستخدمين المميزين."""
    st.title("لوحة التحكم الإدارية 👑")
    st.caption("هذه الصفحة متاحة لك بصفتك مسؤول المشروع.")

    try:
        # جلب جميع المستخدمين (يتطلب إعداد RLS للسماح للمسؤولين بالقراءة)
        response = supabase.table("users").select("*").order("email").execute()
        users = response.data

@@ -273,6 +205,7 @@ def admin_dashboard_ui():
        # إنشاء إطار بيانات (DataFrame) قابل للتعديل
        users_df = pd.DataFrame(users)

        # تصفية الأعمدة وعرضها في جدول Streamlit قابل للتعديل
        edited_df = st.data_editor(
            users_df[['email', 'school_grade', 'is_premium']],
            column_config={
@@ -290,23 +223,23 @@ def admin_dashboard_ui():
            for index, row in edited_df.iterrows():
                original_row = users_df[users_df['email'] == row['email']].iloc[0]

                # التحقق فقط إذا كان قد تم تغيير حالة is_premium
                if original_row['is_premium'] != row['is_premium']:
                    # تحديث Supabase
                    supabase.table("users").update({
                        "is_premium": row['is_premium']
                    }).eq("email", row['email']).execute()

            st.success("تم تحديث صلاحيات الوصول بنجاح!")
            # مسح الكاش لضمان جلب البيانات المحدثة
            get_user_data.clear() 
            st.rerun()

    except Exception as e:
        st.error(f"خطأ في جلب بيانات لوحة التحكم. تأكد من إعداد سياسات الأمان (RLS) للسماح للمسؤولين بالقراءة والتحديث: {e}")


# =========================================================================
# VI. دالة واجهة التطبيق الرئيسية (Main UI) مع البث (Streaming)
# =========================================================================
# -------------------- 6. دالة واجهة التطبيق الرئيسية (Main UI) --------------------

def main_app_ui():
    """عرض واجهة التطبيق الرئيسية (حل المسائل) والتحكم بالتقييد والتخصيص."""
@@ -315,11 +248,10 @@ def main_app_ui():
    st.caption("يرجى التأكد من تحميل صورة عالية الجودة مع نص واضح وتمرين واحد")

    is_premium = st.session_state.get('is_premium', False)
    user_email = st.session_state['user_email']

    # 1. تحديث العداد وعرض حالة الاستخدام
    if not is_premium:
        can_use, current_used = update_user_usage(user_email)
        can_use, current_used = update_user_usage(st.session_state['user_email'])

        st.info(f"الأسئلة المجانية اليومية المتبقية: {MAX_QUESTIONS_DAILY - current_used} من {MAX_QUESTIONS_DAILY}.")

@@ -339,13 +271,12 @@ def main_app_ui():

        if st.button("🚀 ابدأ الحل والتحليل"):

            # استخدام st.status لتقليل الإحساس بالانتظار وتوفير مكان للتدفق
            with st.status("جاري تحليل الصورة وتقديم الحل... (الرد يظهر بالتدفق السريع)", expanded=True) as status:
                
            with st.spinner('يتم تحليل الصورة وتقديم الحل...'):
                try:

                    # 🌟 التعديل الحاسم: تخصيص الحل حسب المستوى 🌟
                    full_user_data = get_user_data(user_email)
                    full_user_data = get_user_data(st.session_state['user_email'])
                    # المستوى الدراسي موجود في حقل 'school_grade'
                    user_grade = full_user_data.get('school_grade', "مستوى غير محدد")

                    # إنشاء تعليمات النظام المخصصة
@@ -358,51 +289,34 @@ def main_app_ui():
                    contents = [custom_prompt, image]
                    # -------------------- 🌟 نهاية التخصيص 🌟 --------------------

                    # 1. استدعاء Gemini في وضع البث (Streaming)
                    stream = client.models.generate_content_stream(
                    response = client.models.generate_content(
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
                        update_user_usage(st.session_state['user_email'], increment=True) 

                    # 4. تحديث حالة الـ status
                    status.update(label="تم تحليل وحل المسألة بنجاح! 🎉", state="complete", expanded=False)
                    st.success("تم تحليل وحل المسألة بنجاح! 🎉")
                    st.subheader("📝 الحل المفصل")
                    st.markdown(response.text)
                    st.rerun()

                except Exception as e:
                    status.update(label="فشل التحليل", state="error", expanded=True)
                    st.error(f"حدث خطأ أثناء الاتصال بالنموذج. تأكد من جودة الصورة: {e}")
                    st.error(f"حدث خطأ أثناء الاتصال بالنموذج: {e}")

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
# -------------------- 7. المنطق الرئيسي للتطبيق (Main) --------------------

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
@@ -428,4 +342,3 @@ def main_app_ui():
    with register_tab:
        register_form()
