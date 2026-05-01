import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import math
import json
import os
import random
import base64
import time

# ========== تهيئة الصفحة ==========
st.set_page_config(
    page_title="Goalify | مساعد الادخار الذكي",
    page_icon="G.png",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ========== دوال حفظ وتحميل البيانات ==========
DATA_FILE = "goals_data.json"
PROFILE_FILE = "profile_data.json"


def get_image_base64(image_path):
    """تحويل الصورة إلى base64 لعرضها في HTML"""
    try:
        if os.path.exists(image_path):
            with open(image_path, "rb") as image_file:
                encoded = base64.b64encode(image_file.read()).decode()
                return f"data:image/png;base64,{encoded}"
        return None
    except Exception:
        return None


def save_goals(goals):
    try:
        goals_to_save = []
        for goal in goals:
            goal_copy = goal.copy()
            if 'end_date' in goal_copy and isinstance(goal_copy['end_date'], datetime):
                goal_copy['end_date'] = goal_copy['end_date'].strftime('%Y-%m-%d')
            if 'created_date' in goal_copy and isinstance(goal_copy['created_date'], datetime):
                goal_copy['created_date'] = goal_copy['created_date'].strftime('%Y-%m-%d')
            if 'completed_date' in goal_copy and isinstance(goal_copy['completed_date'], datetime):
                goal_copy['completed_date'] = goal_copy['completed_date'].strftime('%Y-%m-%d')
            goals_to_save.append(goal_copy)
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(goals_to_save, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"خطأ في حفظ البيانات: {e}")
        return False


def load_goals():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                goals = json.load(f)
            for goal in goals:
                if 'end_date' in goal and goal['end_date']:
                    goal['end_date'] = datetime.strptime(goal['end_date'], '%Y-%m-%d')
                if 'created_date' in goal and goal['created_date']:
                    goal['created_date'] = datetime.strptime(goal['created_date'], '%Y-%m-%d')
                if 'completed_date' in goal and goal['completed_date']:
                    goal['completed_date'] = datetime.strptime(goal['completed_date'], '%Y-%m-%d')
                if 'saved_amount' not in goal:
                    goal['saved_amount'] = 0
                if 'priority' not in goal:
                    goal['priority'] = 'متوسطة'  # عالية، متوسطة، منخفضة
                if 'completed' not in goal:
                    goal['completed'] = False
                if 'essential' not in goal:
                    goal['essential'] = False  # هل الهدف ضروري (مثل سيارة للعمل)؟
            return goals
        return []
    except Exception as e:
        st.error(f"خطأ في تحميل البيانات: {e}")
        return []


def save_profile(profile):
    try:
        with open(PROFILE_FILE, 'w', encoding='utf-8') as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"خطأ في حفظ الملف الشخصي: {e}")
        return False


def load_profile():
    try:
        if os.path.exists(PROFILE_FILE):
            with open(PROFILE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    except Exception as e:
        st.error(f"خطأ في تحميل الملف الشخصي: {e}")
        return None


# ========== التوزيع الذكي حسب الأولوية والمبلغ ==========
def calculate_smart_distribution(goals, monthly_available, emergency_pct=10):
    """
    توزيع ذكي واقعي:
    - يقتطع نسبة للطوارئ
    - يوزع الباقي على الأهداف غير المكتملة
    - الأولوية العالية تأخذ حصة أكبر
    - الأهداف الضرورية تأخذ حصة أكبر
    - الأهداف الصغيرة تنجز أسرع
    """
    if not goals or monthly_available <= 0:
        return [], 0, 0

    # 1. اقتطاع الطوارئ
    emergency_amount = monthly_available * (emergency_pct / 100)
    available_for_goals = monthly_available - emergency_amount

    # 2. الأهداف النشطة (غير المكتملة)
    active_goals = []
    for i, goal in enumerate(goals):
        if goal.get('completed', False):
            continue
        remaining = goal['price'] - goal.get('saved_amount', 0)
        if remaining <= 0:
            goal['completed'] = True
            goal['completed_date'] = datetime.now().strftime('%Y-%m-%d')
            continue
        active_goals.append({
            'index': i,
            'goal': goal,
            'remaining': remaining,
            'priority': goal.get('priority', 'متوسطة'),
            'essential': goal.get('essential', False),
            'price': goal['price']
        })

    if not active_goals:
        return [], emergency_amount, available_for_goals

    # 3. حساب الأوزان حسب الأولوية والضرورة
    priority_weights = {
        'عالية': 3.0,
        'متوسطة': 2.0,
        'منخفضة': 1.0
    }

    for ag in active_goals:
        base_weight = priority_weights.get(ag['priority'], 2.0)
        # الهدف الضروري يأخذ وزن إضافي
        if ag['essential']:
            base_weight *= 1.5
        # الأهداف الصغيرة تأخذ أولوية إضافية بسيطة (تنجز أسرع)
        if ag['remaining'] < monthly_available * 3:
            base_weight *= 1.3
        ag['weight'] = base_weight * ag['remaining']

    total_weight = sum(ag['weight'] for ag in active_goals)

    # 4. توزيع أولي
    distributions = []
    remaining_budget = available_for_goals

    for ag in active_goals:
        fair_share = (ag['weight'] / total_weight) * available_for_goals if total_weight > 0 else 0
        # ما ياخذ أكثر من المتبقي له
        fair_share = min(fair_share, ag['remaining'])
        distributions.append({
            'index': ag['index'],
            'goal_name': ag['goal']['goal_name'],
            'price': ag['price'],
            'saved': ag['goal'].get('saved_amount', 0),
            'remaining': ag['remaining'],
            'monthly_allocation': fair_share,
            'priority': ag['priority'],
            'essential': ag['essential']
        })

    # 5. إعادة توزيع الفائض
    total_allocated = sum(d['monthly_allocation'] for d in distributions)
    leftover = available_for_goals - total_allocated

    if leftover > 0.01:
        # توزيع الفائض على الأهداف اللي لسه محتاجة
        needy = [d for d in distributions if d['remaining'] > d['monthly_allocation']]
        if needy:
            for d in needy:
                extra = leftover / len(needy)
                can_take = d['remaining'] - d['monthly_allocation']
                d['monthly_allocation'] += min(extra, can_take)

    # 6. حساب المدة المتوقعة
    for d in distributions:
        if d['monthly_allocation'] > 0:
            d['months_to_complete'] = d['remaining'] / d['monthly_allocation']
        else:
            d['months_to_complete'] = 999

    # 7. ترتيب حسب الأولوية ثم المدة
    priority_order = {'عالية': 0, 'متوسطة': 1, 'منخفضة': 2}
    distributions.sort(key=lambda x: (priority_order.get(x['priority'], 1), x['months_to_complete']))

    fun_money = leftover if leftover > 0 else 0

    return distributions, emergency_amount, fun_money


# ========== محاكي أزمات واقعي ==========
REALISTIC_CRISES = {
    'فقدان الوظيفة': {
        'icon': '💼',
        'description': 'فقدان مفاجئ للوظيفة وتوقف الدخل لمدة 3-6 أشهر',
        'min_cost': 15000,
        'max_cost': 60000,
        'duration_months': 4,
        'impact': 'يحتاج تغطية 4 أشهر مصاريف = {} ريال',
        'advice': 'ننصح ببناء صندوق طوارئ يغطي 6 أشهر من المصاريف'
    },
    'إصلاح السيارة': {
        'icon': '🔧',
        'description': 'عطل كبير في السيارة يحتاج إصلاح فوري',
        'min_cost': 2000,
        'max_cost': 15000,
        'duration_months': 1,
        'impact': 'تكلفة الإصلاح + تأخير الأهداف بمقدار {} شهر',
        'advice': 'خصص 500 ريال شهرياً لصيانة السيارة'
    },
    'حالة طبية طارئة': {
        'icon': '🏥',
        'description': 'حالة صحية طارئة تتطلب علاج فوري',
        'min_cost': 3000,
        'max_cost': 25000,
        'duration_months': 1,
        'impact': 'تكلفة العلاج + تأخير الأهداف بمقدار {} شهر',
        'advice': 'تأكد من وجود تأمين صحي جيد'
    },
    'إصلاح منزلي': {
        'icon': '🏠',
        'description': 'عطل كبير في المنزل (تكييف، سباكة، كهرباء)',
        'min_cost': 1500,
        'max_cost': 10000,
        'duration_months': 1,
        'impact': 'تكلفة الإصلاح + تأخير الأهداف بمقدار {} شهر',
        'advice': 'خصص 300 ريال شهرياً لصيانة المنزل'
    },
    'نفقة قانونية': {
        'icon': '⚖️',
        'description': 'مصاريف قانونية غير متوقعة (مخالفات، قضايا)',
        'min_cost': 2000,
        'max_cost': 20000,
        'duration_months': 1,
        'impact': 'تكلفة النفقة + تأخير الأهداف بمقدار {} شهر',
        'advice': 'تجنب المخالفات والتزم بالقوانين'
    }
}

# ========== CSS مخصص ==========
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}

    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1200px;
        margin: 0 auto;
    }

    .stApp {
        background: linear-gradient(135deg, #F0F7F4 0%, #E8F0EC 100%);
    }

    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;900&display=swap');

    * {
        font-family: 'Tajawal', sans-serif;
        direction: rtl;
        text-align: right;
    }

    body {
        color: #1a1a1a;
    }

    .logo-container {
        text-align: center;
        margin: 1.5rem 0;
        animation: fadeInUp 0.8s ease;
    }

    .logo-image {
        width: 120px;
        height: 120px;
        border-radius: 50%;
        object-fit: cover;
        box-shadow: 0 8px 30px rgba(27, 94, 32, 0.35);
        border: 4px solid #2E7D32;
        background: white;
        padding: 5px;
        transition: all 0.3s ease;
    }

    .logo-image:hover {
        transform: scale(1.05);
        box-shadow: 0 12px 40px rgba(27, 94, 32, 0.5);
    }

    .logo-small {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        object-fit: cover;
        box-shadow: 0 2px 8px rgba(27, 94, 32, 0.25);
        border: 2px solid #2E7D32;
        background: white;
        padding: 2px;
        vertical-align: middle;
    }

    h1, h2, h3, h4, h5, h6 {
        color: #0D3B0F !important;
        font-weight: 800;
    }

    .goal-card {
        background: #FFFFFF;
        border-radius: 20px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 6px 20px rgba(0,0,0,0.1);
        border: 2px solid #A5D6A7;
        transition: all 0.3s ease;
    }

    .goal-card:hover {
        box-shadow: 0 10px 30px rgba(0,0,0,0.15);
        transform: translateY(-3px);
        border-color: #4CAF50;
    }

    .highlight-card {
        background: linear-gradient(135deg, #0D3B0F 0%, #1B5E20 50%, #2E7D32 100%);
        border-radius: 20px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 6px 25px rgba(27, 94, 32, 0.4);
        text-align: center;
    }

    .highlight-card p,
    .highlight-card span,
    .highlight-card div,
    .highlight-card h1,
    .highlight-card h2,
    .highlight-card h3,
    .highlight-card h4,
    .highlight-card h5,
    .highlight-card h6 {
        color: #FFFFFF !important;
    }

    /* بطاقة الأولوية */
    .priority-high {
        border-right: 6px solid #E53935 !important;
        background: linear-gradient(135deg, #FFFFFF 0%, #FFF5F5 100%) !important;
    }
    .priority-medium {
        border-right: 6px solid #FB8C00 !important;
        background: linear-gradient(135deg, #FFFFFF 0%, #FFF8E1 100%) !important;
    }
    .priority-low {
        border-right: 6px solid #43A047 !important;
        background: linear-gradient(135deg, #FFFFFF 0%, #E8F5E9 100%) !important;
    }
    .priority-essential {
        border-right: 6px solid #8E24AA !important;
        background: linear-gradient(135deg, #FFFFFF 0%, #F3E5F5 100%) !important;
    }

    .priority-badge-high {
        background: #E53935;
        color: white !important;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 700;
    }
    .priority-badge-medium {
        background: #FB8C00;
        color: white !important;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 700;
    }
    .priority-badge-low {
        background: #43A047;
        color: white !important;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 700;
    }
    .essential-badge {
        background: #8E24AA;
        color: white !important;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 700;
    }

    /* إشعار منبثق يختفي */
    .toast-notification {
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 9999;
        background: linear-gradient(135deg, #1B5E20, #2E7D32);
        color: white;
        padding: 1rem 2rem;
        border-radius: 15px;
        font-weight: 700;
        font-size: 1.1rem;
        box-shadow: 0 10px 35px rgba(27,94,32,0.5);
        animation: slideDown 0.5s ease, fadeOut 0.5s ease 2.5s forwards;
        text-align: center;
        max-width: 90%;
    }

    @keyframes slideDown {
        from { top: -100px; opacity: 0; }
        to { top: 20px; opacity: 1; }
    }
    @keyframes fadeOut {
        from { opacity: 1; }
        to { opacity: 0; visibility: hidden; }
    }

    /* احتفال كامل الشاشة */
    .celebration-overlay {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.85);
        z-index: 99999;
        display: flex;
        align-items: center;
        justify-content: center;
        animation: fadeIn 0.5s ease;
    }

    .celebration-content {
        background: linear-gradient(135deg, #FFD700, #FFA000, #FF8F00);
        border-radius: 30px;
        padding: 3rem;
        text-align: center;
        max-width: 600px;
        width: 90%;
        box-shadow: 0 20px 60px rgba(255,215,0,0.6);
        animation: bounceIn 0.8s ease;
        border: 5px solid #FFD700;
    }

    .celebration-content h1 {
        color: #1B5E20 !important;
        font-size: 2.5rem;
        margin: 15px 0;
    }
    .celebration-content p {
        color: #333 !important;
        font-size: 1.2rem;
    }
    .celebration-emoji {
        font-size: 100px;
        animation: pulse 0.5s ease infinite alternate;
    }
    .confetti {
        position: fixed;
        font-size: 40px;
        animation: confettiFall 3s ease forwards;
        z-index: 99999;
        pointer-events: none;
    }

    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    @keyframes bounceIn {
        0% { transform: scale(0.3); opacity: 0; }
        50% { transform: scale(1.05); }
        70% { transform: scale(0.9); }
        100% { transform: scale(1); opacity: 1; }
    }
    @keyframes confettiFall {
        0% { transform: translateY(-100vh) rotate(0deg); opacity: 1; }
        100% { transform: translateY(100vh) rotate(720deg); opacity: 0; }
    }

    .saved-goal-card {
        background: #FFFFFF;
        border-radius: 20px;
        padding: 1.2rem;
        margin: 0.8rem 0;
        box-shadow: 0 3px 15px rgba(0,0,0,0.08);
        border: 2px solid #C8E6C9;
        border-right: 6px solid #2E7D32;
        transition: all 0.3s ease;
    }

    .saved-goal-card:hover {
        box-shadow: 0 8px 25px rgba(0,0,0,0.12);
        transform: translateX(-5px);
    }

    .distribution-card {
        background: #FFFFFF;
        border-radius: 16px;
        padding: 1rem 1.3rem;
        margin: 0.6rem 0;
        box-shadow: 0 3px 12px rgba(0,0,0,0.06);
        border: 2px solid #C8E6C9;
        transition: all 0.3s ease;
    }

    .distribution-card:hover {
        transform: translateX(-3px);
        box-shadow: 0 6px 18px rgba(0,0,0,0.1);
    }

    .emergency-badge {
        background: linear-gradient(135deg, #FFF8E1, #FFE082);
        color: #E65100 !important;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: 700;
        display: inline-block;
        border: 2px solid #FF9800;
        font-size: 0.9rem;
    }

    .warning-card {
        background: linear-gradient(135deg, #FFF8E1 0%, #FFECB3 100%);
        border-radius: 20px;
        padding: 1.2rem;
        margin: 1rem 0;
        text-align: center;
        border: 2px solid #FF9800;
    }

    .warning-card p, .warning-card span {
        color: #E65100 !important;
        font-weight: 700;
    }

    .danger-card {
        background: linear-gradient(135deg, #FFEBEE 0%, #FFCDD2 100%);
        border-radius: 20px;
        padding: 1.2rem;
        margin: 1rem 0;
        text-align: center;
        border: 2px solid #EF5350;
    }

    .danger-card p, .danger-card span {
        color: #B71C1C !important;
        font-weight: 700;
    }

    .success-card {
        background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 100%);
        border-radius: 20px;
        padding: 1.2rem;
        margin: 1rem 0;
        text-align: center;
        border: 2px solid #388E3C;
    }

    .success-card p, .success-card span {
        color: #0D3B0F !important;
        font-weight: 700;
    }

    .crisis-card {
        background: #FFFFFF;
        border-radius: 20px;
        padding: 1.5rem;
        margin: 1rem 0;
        border: 2px solid #FFCDD2;
        box-shadow: 0 6px 20px rgba(198,40,40,0.15);
        transition: all 0.3s ease;
        cursor: pointer;
    }

    .crisis-card:hover {
        box-shadow: 0 10px 30px rgba(198,40,40,0.25);
        transform: translateY(-3px);
        border-color: #EF5350;
    }

    .tip-card {
        background: #FFFFFF;
        border-radius: 16px;
        padding: 1.2rem 1.5rem;
        margin: 0.8rem 0;
        border: 2px solid #C8E6C9;
        border-right: 5px solid #2E7D32;
        box-shadow: 0 3px 15px rgba(0,0,0,0.06);
        transition: all 0.3s ease;
        animation: fadeInUp 0.5s ease;
    }

    .tip-card:hover {
        transform: translateX(-5px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.1);
        border-right-width: 8px;
        border-right-color: #1B5E20;
    }

    .tip-badge {
        background: linear-gradient(135deg, #E8F5E9, #C8E6C9);
        color: #1B5E20 !important;
        padding: 0.35rem 0.9rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 700;
        display: inline-block;
        border: 1.5px solid #4CAF50;
    }

    .stButton > button {
        border-radius: 25px !important;
        padding: 0.65rem 1.5rem !important;
        font-size: 0.95rem !important;
        font-weight: 700 !important;
        background: linear-gradient(135deg, #1B5E20 0%, #388E3C 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 3px 12px rgba(27, 94, 32, 0.35);
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 22px rgba(27, 94, 32, 0.45) !important;
        background: linear-gradient(135deg, #2E7D32 0%, #43A047 100%) !important;
    }

    button[key*="del_"] {
        background: linear-gradient(135deg, #C62828 0%, #EF5350 100%) !important;
        box-shadow: 0 3px 12px rgba(198, 40, 40, 0.35) !important;
        color: #FFFFFF !important;
        font-weight: 800 !important;
    }

    button[key*="del_"]:hover {
        background: linear-gradient(135deg, #B71C1C 0%, #D32F2F 100%) !important;
        box-shadow: 0 6px 22px rgba(198, 40, 40, 0.5) !important;
        transform: translateY(-2px) !important;
    }

    button[key*="delete_profile"] {
        background: linear-gradient(135deg, #C62828 0%, #EF5350 100%) !important;
        box-shadow: 0 3px 12px rgba(198, 40, 40, 0.35) !important;
        color: #FFFFFF !important;
        font-weight: 800 !important;
    }

    button[key*="delete_profile"]:hover {
        background: linear-gradient(135deg, #B71C1C 0%, #D32F2F 100%) !important;
        box-shadow: 0 6px 22px rgba(198, 40, 40, 0.5) !important;
        transform: translateY(-2px) !important;
    }

    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stTextArea > div > div > textarea {
        border-radius: 15px !important;
        border: 2.5px solid #66BB6A !important;
        padding: 0.7rem 1rem !important;
        font-size: 0.95rem !important;
        background: #FFFFFF !important;
        color: #111111 !important;
        font-weight: 500;
        text-align: right !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
    }

    .stSelectbox > div > div {
        border-radius: 15px !important;
        border: 2.5px solid #66BB6A !important;
        background: #FFFFFF !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
    }

    .custom-progress {
        background: #BDBDBD;
        border-radius: 15px;
        height: 14px;
        overflow: hidden;
        margin: 10px 0;
        box-shadow: inset 0 2px 5px rgba(0,0,0,0.1);
    }

    .custom-progress-bar {
        background: linear-gradient(90deg, #0D3B0F, #2E7D32, #4CAF50);
        height: 100%;
        border-radius: 15px;
        transition: width 0.5s ease;
        box-shadow: 0 2px 8px rgba(27, 94, 32, 0.3);
    }

    .custom-progress-bar-fast {
        background: linear-gradient(90deg, #FF8F00, #FFB300, #FFCA28);
        height: 100%;
        border-radius: 15px;
        transition: width 0.5s ease;
        box-shadow: 0 2px 8px rgba(255, 143, 0, 0.3);
    }

    .custom-progress-bar-done {
        background: linear-gradient(90deg, #2E7D32, #43A047, #66BB6A);
        height: 100%;
        border-radius: 15px;
        transition: width 0.5s ease;
        box-shadow: 0 2px 8px rgba(46, 125, 50, 0.3);
    }

    .field-label {
        color: #0D3B0F !important;
        font-weight: 700;
        margin-bottom: 0.5rem;
        font-size: 1rem;
    }

    .info-label {
        color: #444444 !important;
        font-size: 0.85rem;
        font-weight: 600;
    }

    .info-value {
        color: #0D3B0F !important;
        font-weight: 800;
        font-size: 1rem;
    }

    .status-success { 
        background: linear-gradient(135deg, #E8F5E9, #A5D6A7);
        color: #0D3B0F !important; 
        font-weight: 800; 
        padding: 1rem;
        border-radius: 15px;
        text-align: center;
        border: 2.5px solid #388E3C;
        font-size: 1.05rem;
    }
    .status-warning { 
        background: linear-gradient(135deg, #FFF8E1, #FFE082);
        color: #E65100 !important; 
        font-weight: 800; 
        padding: 1rem;
        border-radius: 15px;
        text-align: center;
        border: 2.5px solid #FF9800;
        font-size: 1.05rem;
    }
    .status-danger { 
        background: linear-gradient(135deg, #FFEBEE, #EF9A9A);
        color: #B71C1C !important; 
        font-weight: 800; 
        padding: 1rem;
        border-radius: 15px;
        text-align: center;
        border: 2.5px solid #EF5350;
        font-size: 1.05rem;
    }

    .balance-circle {
        width: 130px;
        height: 130px;
        border-radius: 50%;
        background: linear-gradient(135deg, #0D3B0F, #2E7D32);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin: 1rem auto;
        box-shadow: 0 8px 28px rgba(27, 94, 32, 0.4);
    }

    [data-testid="stMetricValue"] {
        color: #0D3B0F !important;
        font-weight: 900 !important;
    }

    [data-testid="stMetricLabel"] {
        color: #444444 !important;
        font-weight: 600 !important;
    }

    .remaining-text {
        color: #B71C1C !important;
        font-weight: 800;
        font-size: 1rem;
    }

    .budget-box {
        background: linear-gradient(135deg, #E8F5E9 0%, #C8E6C9 100%);
        border-radius: 20px;
        padding: 2rem;
        text-align: center;
        margin: 1.5rem 0;
        border: 2.5px solid #4CAF50;
    }

    .budget-amount {
        font-size: 2.5rem;
        font-weight: 900;
        color: #0D3B0F;
        margin: 0.5rem 0;
    }

    .budget-breakdown {
        display: flex;
        justify-content: space-around;
        margin: 1.5rem 0;
        flex-wrap: wrap;
        gap: 10px;
    }

    .budget-item {
        background: white;
        border-radius: 15px;
        padding: 1rem;
        text-align: center;
        flex: 1;
        min-width: 100px;
        box-shadow: 0 3px 10px rgba(0,0,0,0.08);
    }

    @media (max-width: 768px) {
        .goal-card, .saved-goal-card {
            padding: 1rem;
        }
        .balance-circle {
            width: 100px;
            height: 100px;
        }
        .logo-image {
            width: 90px;
            height: 90px;
        }
        .budget-amount {
            font-size: 2rem;
        }
        .celebration-emoji {
            font-size: 70px;
        }
        .celebration-content h1 {
            font-size: 1.8rem;
        }
    }

    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }

    @keyframes pulse {
        0% { transform: scale(1); }
        100% { transform: scale(1.1); }
    }

    .goal-card, .saved-goal-card, .highlight-card, .distribution-card, .crisis-card {
        animation: fadeInUp 0.5s ease;
    }

    .logo-image {
        animation: pulse 3s ease-in-out infinite;
    }

    @keyframes float {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-10px); }
    }
</style>
""", unsafe_allow_html=True)


# ========== دوال JavaScript للاحتفال والإشعارات ==========
def show_celebration(goal_name: str, goal_emoji: str):
    """عرض احتفال كامل الشاشة"""
    confetti_emojis = ['🎉', '🎊', '✨', '🌟', '💫', '🎯', '🏆', '💎', '🥇', '🎈', '🎀', '👏', '🔥', '💚', '💰']

    js_code = f"""
    <script>
    // إنشاء طبقة الاحتفال
    const overlay = document.createElement('div');
    overlay.className = 'celebration-overlay';
    overlay.id = 'celebration-overlay';

    const content = document.createElement('div');
    content.className = 'celebration-content';
    content.innerHTML = `
        <div class="celebration-emoji">{goal_emoji}</div>
        <h1>🎉 مبروك! 🎉</h1>
        <p style="font-size: 1.5rem; font-weight: 800; color: #1B5E20;">حققت هدفك!</p>
        <p style="font-size: 1.8rem; font-weight: 900; color: #0D3B0F;">{goal_name}</p>
        <p style="color: #555;">استمر في الادخار لأهدافك القادمة 💪</p>
        <button onclick="document.getElementById('celebration-overlay').remove();" 
                style="background: #1B5E20; color: white; border: none; padding: 12px 30px; 
                border-radius: 25px; font-size: 1.1rem; font-weight: 700; cursor: pointer;
                margin-top: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
            ✨ شكراً
        </button>
    `;

    overlay.appendChild(content);
    document.body.appendChild(overlay);

    // قصاصات ملونة
    const emojis = {confetti_emojis};
    for (let i = 0; i < 50; i++) {{
        setTimeout(() => {{
            const confetti = document.createElement('div');
            confetti.className = 'confetti';
            confetti.textContent = emojis[Math.floor(Math.random() * emojis.length)];
            confetti.style.left = Math.random() * 100 + '%';
            confetti.style.top = -(Math.random() * 100) + 'px';
            confetti.style.animationDuration = (Math.random() * 2 + 2) + 's';
            confetti.style.animationDelay = Math.random() * 0.5 + 's';
            document.body.appendChild(confetti);

            setTimeout(() => confetti.remove(), 3500);
        }}, i * 40);
    }}

    // إزالة تلقائية بعد 6 ثواني
    setTimeout(() => {{
        const ov = document.getElementById('celebration-overlay');
        if (ov) ov.remove();
    }}, 6000);
    </script>
    """
    st.components.v1.html(js_code, height=0)


def show_toast(message: str):
    """عرض إشعار يختفي بعد 3 ثواني"""
    js_code = f"""
    <script>
    const toast = document.createElement('div');
    toast.className = 'toast-notification';
    toast.textContent = '{message}';
    document.body.appendChild(toast);

    // إزالة بعد 3 ثواني
    setTimeout(() => {{
        if (toast) toast.remove();
    }}, 3000);
    </script>
    """
    st.components.v1.html(js_code, height=0)


# ========== تهيئة session_state ==========
if 'goals' not in st.session_state:
    st.session_state.goals = load_goals()
if 'profile' not in st.session_state:
    st.session_state.profile = load_profile()
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'home'
if 'editing_goal' not in st.session_state:
    st.session_state.editing_goal = None
if 'delete_profile_confirm' not in st.session_state:
    st.session_state.delete_profile_confirm = False
if 'last_goals_count' not in st.session_state:
    st.session_state.last_goals_count = len([g for g in st.session_state.goals if g.get('completed')])
if 'show_celebration_for' not in st.session_state:
    st.session_state.show_celebration_for = None

# ========== تحميل صورة الشعار ==========
LOGO_PATH = "G.png"
logo_base64 = get_image_base64(LOGO_PATH)


# ========== دوال مساعدة ==========
def format_currency(amount):
    return f"{amount:,.0f}"


def get_goal_emoji(goal_name):
    goal_lower = goal_name.lower()
    emoji_map = {
        'سفر': '✈️', 'طيران': '✈️', 'عطلة': '✈️', 'سياحة': '✈️',
        'سيارة': '🚗', 'موتر': '🚗', 'تسلا': '🚗',
        'منزل': '🏠', 'بيت': '🏠', 'شقة': '🏠', 'فيلا': '🏠',
        'لابتوب': '💻', 'كمبيوتر': '💻', 'جوال': '📱', 'ايفون': '📱',
        'زواج': '💒', 'عرس': '💒',
        'تعليم': '📚', 'دورة': '📚', 'جامعة': '📚',
        'مشروع': '💼', 'تجارة': '💼', 'استثمار': '💼',
        'ديون': '💳', 'قرض': '💳',
        'صحة': '🏥', 'علاج': '🏥',
        'أثاث': '🛋️', 'اجهزة': '📺'
    }
    for key, emoji in emoji_map.items():
        if key in goal_lower:
            return emoji
    return '🎯'


def update_saved_amount(goal_index, amount):
    if 0 <= goal_index < len(st.session_state.goals):
        current_saved = st.session_state.goals[goal_index].get('saved_amount', 0)
        new_total = current_saved + amount
        st.session_state.goals[goal_index]['saved_amount'] = new_total

        # التحقق إذا اكتمل الهدف
        if new_total >= st.session_state.goals[goal_index]['price']:
            st.session_state.goals[goal_index]['completed'] = True
            st.session_state.goals[goal_index]['completed_date'] = datetime.now().strftime('%Y-%m-%d')
            st.session_state.show_celebration_for = goal_index

        save_goals(st.session_state.goals)
        return True
    return False


def delete_goal(index):
    if 0 <= index < len(st.session_state.goals):
        del st.session_state.goals[index]
        save_goals(st.session_state.goals)
        st.rerun()


def delete_profile():
    st.session_state.profile = None
    if os.path.exists(PROFILE_FILE):
        os.remove(PROFILE_FILE)
    st.session_state.delete_profile_confirm = False
    st.rerun()


def custom_progress_bar(percentage, height="14px", bar_class="custom-progress-bar"):
    pct = min(max(percentage, 0), 100)
    return f'<div class="custom-progress" style="height: {height};"><div class="{bar_class}" style="width: {pct}%;"></div></div>'


def render_logo(size="large"):
    if logo_base64:
        if size == "large":
            return f'<div class="logo-container"><img src="{logo_base64}" class="logo-image" alt="Goalify Logo"></div>'
        else:
            return f'<img src="{logo_base64}" class="logo-small" alt="Goalify Logo">'
    else:
        if size == "large":
            return '<div class="logo-container"><span style="font-size: 70px;">🥑</span></div>'
        else:
            return '<span style="font-size: 25px;">🥑</span>'


def format_timeline(months):
    """تنسيق المدة الزمنية بشكل واقعي"""
    if months >= 999:
        return "أكثر من 10 سنوات"
    if months <= 0.5:
        return "أقل من شهر"

    years = int(months // 12)
    rem_months = round(months % 12)

    if years == 0:
        if rem_months == 1:
            return "شهر واحد"
        elif rem_months == 2:
            return "شهرين"
        elif rem_months <= 10:
            return f"{rem_months} شهور"
        else:
            return f"{rem_months} شهر"
    elif years == 1:
        if rem_months == 0:
            return "سنة واحدة"
        elif rem_months == 1:
            return "سنة و شهر"
        else:
            return f"سنة و {rem_months} شهور"
    elif years <= 10:
        if rem_months == 0:
            return f"{years} سنوات"
        else:
            return f"{years} سنوات و {rem_months} شهور"
    else:
        return "أكثر من 10 سنوات"


def get_priority_color(priority, essential=False):
    if essential:
        return 'priority-essential', 'essential-badge', '⚡ ضروري'
    if priority == 'عالية':
        return 'priority-high', 'priority-badge-high', '🔴 عالية'
    elif priority == 'منخفضة':
        return 'priority-low', 'priority-badge-low', '🟢 منخفضة'
    else:
        return 'priority-medium', 'priority-badge-medium', '🟠 متوسطة'


# ========== الصفحة الرئيسية ==========
def show_home_page():
    # عرض رسالة الإشعار إن وجدت
    if 'toast_message' in st.session_state and st.session_state.toast_message:
        show_toast(st.session_state.toast_message)
        st.session_state.toast_message = None

    # عرض احتفال إذا تم تحقيق هدف
    if st.session_state.show_celebration_for is not None:
        idx = st.session_state.show_celebration_for
        if idx < len(st.session_state.goals):
            goal = st.session_state.goals[idx]
            emoji = get_goal_emoji(goal['goal_name'])
            show_celebration(goal['goal_name'], emoji)
        st.session_state.show_celebration_for = None

    st.markdown(render_logo("large"), unsafe_allow_html=True)
    st.markdown(
        '<h1 style="color: #0D3B0F; font-weight: 900; margin: 0; font-size: 2.2rem; text-align: center;">Goalify</h1>',
        unsafe_allow_html=True)
    st.markdown(
        '<p style="color: #1B5E20; font-size: 1rem; text-align: center; font-weight: 500;">مساعدك الذكي لتحقيق أهدافك المالية</p>',
        unsafe_allow_html=True)

    profile = st.session_state.profile
    goals = st.session_state.goals

    # --- الملف الشخصي موجود ---
    if profile and profile.get('monthly_income', 0) > 0:
        monthly_income = profile['monthly_income']
        monthly_expenses = profile.get('essential_expenses', 0)
        remaining = monthly_income - monthly_expenses

        if remaining <= 0:
            st.markdown(f"""
            <div class="danger-card">
                <p style="font-size: 1.3rem;">⚠️ تنبيه!</p>
                <p>مصاريفك ({format_currency(monthly_expenses)}) أكبر من أو تساوي راتبك ({format_currency(monthly_income)})</p>
                <p>المتبقي: {format_currency(remaining)} ريال - لن تتمكن من الادخار</p>
                <p style="font-size: 0.85rem;">💡 الحل: قلل مصاريفك أو ابحث عن دخل إضافي</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            # التوزيع الذكي
            distributions, emergency_amount, fun_money = calculate_smart_distribution(goals, remaining)

            total_for_goals = sum(d['monthly_allocation'] for d in distributions)

            # الميزانية الذكية
            st.markdown(f"""
            <div class="budget-box">
                <h3 style="margin: 0 0 15px 0; font-weight: 900;">💰 ميزانيتك الشهرية الذكية</h3>
                <div class="budget-breakdown">
                    <div class="budget-item">
                        <div style="font-size: 30px;">🏠</div>
                        <p style="color: #E65100; font-weight: 700; margin: 5px 0;">ضروريات</p>
                        <p style="font-size: 1.2rem; font-weight: 900; color: #E65100;">{format_currency(monthly_expenses)}</p>
                        <p style="font-size: 0.7rem; color: #888;">{round(monthly_expenses / monthly_income * 100)}% من الراتب</p>
                    </div>
                    <div class="budget-item">
                        <div style="font-size: 30px;">🎯</div>
                        <p style="color: #1B5E20; font-weight: 700; margin: 5px 0;">أهداف</p>
                        <p style="font-size: 1.2rem; font-weight: 900; color: #1B5E20;">{format_currency(total_for_goals)}</p>
                        <p style="font-size: 0.7rem; color: #888;">{len(distributions)} أهداف نشطة</p>
                    </div>
                    <div class="budget-item">
                        <div style="font-size: 30px;">🛡️</div>
                        <p style="color: #E65100; font-weight: 700; margin: 5px 0;">طوارئ</p>
                        <p style="font-size: 1.2rem; font-weight: 900; color: #E65100;">{format_currency(emergency_amount)}</p>
                        <p style="font-size: 0.7rem; color: #888;">10% تلقائياً</p>
                    </div>
                    <div class="budget-item">
                        <div style="font-size: 30px;">🎉</div>
                        <p style="color: #1565C0; font-weight: 700; margin: 5px 0;">حر</p>
                        <p style="font-size: 1.2rem; font-weight: 900; color: #1565C0;">{format_currency(fun_money)}</p>
                        <p style="font-size: 0.7rem; color: #888;">كماليات وترفيه</p>
                    </div>
                </div>
                <p style="color: #444444; font-size: 0.85rem;">الراتب: {format_currency(monthly_income)} | المتبقي: {format_currency(remaining)}</p>
            </div>
            """, unsafe_allow_html=True)

            # عرض التوزيع على الأهداف
            if distributions:
                st.markdown(
                    f'<h3 style="color: #0D3B0F; text-align: center; margin: 1.2rem 0;">📋 خطة تحقيق الأهداف</h3>',
                    unsafe_allow_html=True)

                for d in distributions:
                    emoji = get_goal_emoji(d['goal_name'])
                    progress = (d['saved'] / d['price'] * 100) if d['price'] > 0 else 0
                    bar_class = "custom-progress-bar"
                    if d['months_to_complete'] <= 3:
                        bar_class = "custom-progress-bar-fast"
                    if progress >= 100:
                        bar_class = "custom-progress-bar-done"

                    priority_class, badge_class, badge_text = get_priority_color(d['priority'], d['essential'])

                    st.markdown(f"""
                    <div class="distribution-card {priority_class}">
                        <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                            <div style="font-size: 35px; min-width: 45px; text-align: center;">{emoji}</div>
                            <div style="flex: 1; min-width: 180px;">
                                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 5px;">
                                    <div style="display: flex; align-items: center; gap: 6px;">
                                        <h4 style="margin: 0; font-weight: 800; font-size: 1rem;">{d['goal_name']}</h4>
                                        <span class="{badge_class}">{badge_text}</span>
                                    </div>
                                    <span style="color: #1B5E20; font-weight: 800; font-size: 0.95rem;">💵 {format_currency(d['monthly_allocation'])}/شهر</span>
                                </div>
                                <div style="display: flex; justify-content: space-between; margin: 5px 0; flex-wrap: wrap;">
                                    <span style="color: #444444; font-size: 0.8rem;">💰 {format_currency(d['saved'])} من {format_currency(d['price'])}</span>
                                    <span style="color: #E65100; font-weight: 700; font-size: 0.85rem;">⏱️ {format_timeline(d['months_to_complete'])}</span>
                                </div>
                                {custom_progress_bar(progress, "10px", bar_class)}
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                if goals:
                    st.markdown("""
                    <div class="success-card">
                        <p style="font-size: 1.3rem;">🎉 مبروك!</p>
                        <p>كل أهدافك مكتملة! أضف أهدافاً جديدة واستمر في الادخار</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div style="background: #FFFFFF; border-radius: 20px; padding: 2rem; margin: 1rem 0; text-align: center; box-shadow: 0 6px 20px rgba(0,0,0,0.08); border: 2px solid #C8E6C9;">
                        <div style="font-size: 60px;">🎯</div>
                        <p style="color: #333333; font-size: 1.1rem; font-weight: 600;">لا توجد أهداف حالياً</p>
                        <p style="color: #555555;">أضف هدفك الأول وشوف كيف راح يتحقق!</p>
                    </div>
                    """, unsafe_allow_html=True)

    # --- لا يوجد ملف شخصي ---
    else:
        st.markdown("""
        <div class="warning-card">
            <p style="font-size: 1.3rem;">👋 أهلًا بك!</p>
            <p>عشان نقدر نساعدك، نحتاج تعبي ملفك الشخصي أولاً</p>
            <p style="font-size: 0.9rem;">معلومتين فقط: الراتب الشهري + مصاريفك الأساسية</p>
        </div>
        """, unsafe_allow_html=True)

        # عرض الأهداف للمستخدم بدون ملف شخصي
        if goals:
            st.markdown(
                f'<h3 style="color: #0D3B0F; text-align: center; margin: 1.2rem 0;">📋 أهدافك ({len(goals)})</h3>',
                unsafe_allow_html=True)
            active_goals = [g for g in goals if not g.get('completed')]
            completed_goals = [g for g in goals if g.get('completed')]

            if completed_goals:
                st.markdown(f'<p style="color: #2E7D32; font-weight: 700;">✅ مكتملة: {len(completed_goals)}</p>',
                            unsafe_allow_html=True)

            for i, goal in enumerate(goals):
                saved = goal.get('saved_amount', 0)
                progress = (saved / goal['price'] * 100) if goal['price'] > 0 else 0
                emoji = get_goal_emoji(goal['goal_name'])
                completed = goal.get('completed', False)

                card_style = 'border-right: 6px solid #4CAF50;' if completed else ''
                if completed:
                    card_style += ' background: linear-gradient(135deg, #FFFFFF 0%, #E8F5E9 100%);'

                st.markdown(f"""
                <div class="saved-goal-card" style="{card_style}">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <div style="font-size: 35px;">{emoji}</div>
                        <div style="flex: 1;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <h4 style="margin: 0; font-weight: 800;">{goal['goal_name']}</h4>
                                {f'<span style="background: #4CAF50; color: white; padding: 2px 10px; border-radius: 10px; font-size: 0.7rem;">✅ مكتمل</span>' if completed else ''}
                            </div>
                            <p style="margin: 3px 0; color: #444;">💰 {format_currency(goal['price'])} ريال | المدخر: {format_currency(saved)}</p>
                            {custom_progress_bar(progress, "10px")}
                        </div>
                        <div>
                            <span style="font-size: 0.8rem; font-weight: 700;">{round(progress)}%</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # أزرار التنقل
    st.markdown('<br>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("👤 ملفي الشخصي", use_container_width=True):
            st.session_state.current_page = 'profile'
            st.rerun()
    with col2:
        if st.button("➕ هدف جديد", use_container_width=True):
            st.session_state.current_page = 'add_goal'
            st.rerun()
    with col3:
        if st.button("💡 نصائح ذكية", use_container_width=True):
            st.session_state.current_page = 'tips'
            st.rerun()

    # أزرار سريعة لكل هدف
    if goals:
        st.markdown('<hr style="margin: 1.5rem 0; border-color: #C8E6C9;">', unsafe_allow_html=True)
        st.markdown('<p style="text-align: center; color: #666; font-weight: 600;">⚡ إجراءات سريعة لأهدافك</p>',
                    unsafe_allow_html=True)
        for i, goal in enumerate(goals):
            if goal.get('completed', False):
                continue
            emoji = get_goal_emoji(goal['goal_name'])
            saved = goal.get('saved_amount', 0)
            with st.expander(
                    f"{emoji} {goal['goal_name']} ({format_currency(saved)} / {format_currency(goal['price'])})"):
                btn_col1, btn_col2, btn_col3, btn_col4 = st.columns([2, 2, 2, 1])
                with btn_col1:
                    if st.button("📊 تفاصيل", key=f"view_{i}", use_container_width=True):
                        st.session_state.editing_goal = i
                        st.session_state.current_page = 'results'
                        st.rerun()
                with btn_col2:
                    if st.button("💰 إيداع", key=f"dep_{i}", use_container_width=True):
                        st.session_state.editing_goal = i
                        st.session_state.current_page = 'deposit'
                        st.rerun()
                with btn_col3:
                    if st.button("⚠️ محاكاة أزمة", key=f"crs_{i}", use_container_width=True):
                        st.session_state.editing_goal = i
                        st.session_state.current_page = 'simulator'
                        st.rerun()
                with btn_col4:
                    if st.button("🗑", key=f"del_{i}", use_container_width=True):
                        delete_goal(i)

    st.markdown(
        f'<div style="text-align: center; margin-top: 2.5rem; padding: 1rem;">{render_logo("small")} <span style="margin-right: 10px; color: #555555; font-weight: 600;">Goalify © 2026 | النسخة الذكية</span></div>',
        unsafe_allow_html=True)


# ========== صفحة الملف الشخصي ==========
def show_profile_page():
    st.markdown(
        f'{render_logo("small")}<h2 style="color: #0D3B0F; display: inline; margin-right: 10px; font-weight: 900;">ملفي الشخصي</h2>',
        unsafe_allow_html=True)
    st.markdown('<p style="color: #444444; font-weight: 500;">معلومتين فقط - ونتولى توزيع مدخراتك بذكاء</p>',
                unsafe_allow_html=True)

    profile = st.session_state.profile or {'monthly_income': 0, 'essential_expenses': 0}

    with st.container():
        st.markdown('<div class="goal-card">', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<p class="field-label">💰 الراتب الشهري (ريال)</p>', unsafe_allow_html=True)
            monthly_income = st.number_input(
                "الراتب",
                min_value=0,
                max_value=1000000,
                value=profile.get('monthly_income', 0) if profile.get('monthly_income', 0) > 0 else None,
                step=500,
                placeholder="أدخل راتبك...",
                label_visibility="collapsed"
            )
        with col2:
            st.markdown('<p class="field-label">🏠 إجمالي المصاريف الأساسية (ريال)</p>', unsafe_allow_html=True)
            st.markdown(
                '<p style="font-size: 0.75rem; color: #888;">الإيجار، الفواتير، الأكل، المواصلات، الأقساط...</p>',
                unsafe_allow_html=True)
            essential_expenses = st.number_input(
                "المصاريف",
                min_value=0,
                max_value=1000000,
                value=profile.get('essential_expenses', 0) if profile.get('essential_expenses', 0) > 0 else None,
                step=200,
                placeholder="أدخل مصاريفك...",
                label_visibility="collapsed"
            )

        st.markdown('</div>', unsafe_allow_html=True)

    # معاينة
    if monthly_income and monthly_income > 0:
        remaining = monthly_income - (essential_expenses or 0)
        emergency_amount = remaining * 0.10
        goals_amount = remaining - emergency_amount

        status = "success-card" if remaining > 0 else "danger-card"
        emoji_status = "✅" if remaining > 0 else "⚠️"

        st.markdown(f"""
        <div class="{status}">
            <p style="font-size: 1.2rem;">{emoji_status} تحليل وضعك المالي</p>
            <div style="display: flex; justify-content: space-around; flex-wrap: wrap; gap: 15px; margin: 1rem 0;">
                <div>
                    <p style="color: #666; font-size: 0.8rem;">المتبقي للادخار</p>
                    <p style="font-size: 1.5rem; font-weight: 900; color: {'#E65100' if remaining <= 0 else '#1B5E20'};">{format_currency(remaining)}</p>
                </div>
                <div>
                    <p style="color: #666; font-size: 0.8rem;">للأهداف</p>
                    <p style="font-size: 1.5rem; font-weight: 900; color: #1B5E20;">{format_currency(goals_amount)}</p>
                </div>
                <div>
                    <p style="color: #666; font-size: 0.8rem;">للطوارئ (10%)</p>
                    <p style="font-size: 1.5rem; font-weight: 900; color: #E65100;">{format_currency(emergency_amount)}</p>
                </div>
            </div>
            <p style="color: #444; font-size: 0.8rem;">{"👍 وضعك ممتاز - فائض للادخار" if remaining > 0 else "👎 المصاريف تستهلك كل الراتب - تحتاج مراجعة"}</p>
        </div>
        """, unsafe_allow_html=True)

    # أزرار
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 حفظ الملف الشخصي", use_container_width=True):
            if monthly_income is not None and monthly_income > 0:
                st.session_state.profile = {
                    'monthly_income': monthly_income,
                    'essential_expenses': essential_expenses or 0
                }
                if save_profile(st.session_state.profile):
                    st.session_state.toast_message = "✅ تم حفظ الملف الشخصي بنجاح!"
                    st.session_state.current_page = 'home'
                    st.rerun()
            else:
                st.error("⚠️ الرجاء إدخال الراتب")
    with col2:
        if st.session_state.profile:
            if not st.session_state.delete_profile_confirm:
                if st.button("🗑 حذف الملف الشخصي", use_container_width=True, key="delete_profile_btn"):
                    st.session_state.delete_profile_confirm = True
                    st.rerun()
            else:
                st.markdown("""
                <div class="danger-card" style="padding: 0.8rem; margin: 0.5rem 0;">
                    <p style="font-size: 0.9rem;">⚠️ هل أنت متأكد من حذف الملف الشخصي؟</p>
                    <p style="font-size: 0.8rem;">أهدافك راح تبقى محفوظة</p>
                </div>
                """, unsafe_allow_html=True)
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ نعم، احذف", use_container_width=True, key="confirm_delete"):
                        delete_profile()
                        st.session_state.toast_message = "🗑 تم حذف الملف الشخصي"
                        st.session_state.current_page = 'home'
                        st.rerun()
                with col_no:
                    if st.button("❌ إلغاء", use_container_width=True, key="cancel_delete"):
                        st.session_state.delete_profile_confirm = False
                        st.rerun()

    if st.button("← العودة للرئيسية", use_container_width=True):
        st.session_state.delete_profile_confirm = False
        st.session_state.current_page = 'home'
        st.rerun()


# ========== صفحة إضافة هدف ==========
def show_add_goal_page():
    st.markdown(
        f'{render_logo("small")}<h2 style="color: #0D3B0F; display: inline; margin-right: 10px; font-weight: 900;">إضافة هدف جديد</h2>',
        unsafe_allow_html=True)

    profile = st.session_state.profile

    if not profile or profile.get('monthly_income', 0) <= 0:
        st.markdown("""
        <div class="warning-card">
            <p style="font-size: 1.3rem;">⚠️ تنبيه!</p>
            <p>يجب إعداد ملفك الشخصي أولاً لتتمكن من إضافة هدف ومعرفة المدة المتوقعة</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("👤 إعداد الملف الشخصي", use_container_width=True):
            st.session_state.current_page = 'profile'
            st.rerun()
        if st.button("← العودة للرئيسية", use_container_width=True):
            st.session_state.current_page = 'home'
            st.rerun()
        return

    monthly_income = profile['monthly_income']
    monthly_expenses = profile.get('essential_expenses', 0)
    remaining = monthly_income - monthly_expenses

    if remaining <= 0:
        st.markdown(f"""
        <div class="danger-card">
            <p style="font-size: 1.3rem;">⚠️ لا يوجد فائض للادخار</p>
            <p>المتبقي من راتبك: {format_currency(remaining)} ريال</p>
            <p>يجب تقليل المصاريف أو زيادة الدخل قبل إضافة أهداف جديدة</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("← العودة للرئيسية", use_container_width=True):
            st.session_state.current_page = 'home'
            st.rerun()
        return

    with st.container():
        st.markdown('<div class="goal-card">', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<p class="field-label">🎯 اسم الهدف</p>', unsafe_allow_html=True)
            goal_name = st.text_input("اسم_الهدف", placeholder="مثال: لابتوب ماك بوك...", label_visibility="collapsed")
        with col2:
            st.markdown('<p class="field-label">💰 سعر الهدف (ريال)</p>', unsafe_allow_html=True)
            price = st.number_input("السعر", min_value=100, max_value=10000000, step=100, value=None,
                                    placeholder="مثال: 5000", label_visibility="collapsed")

        col3, col4 = st.columns(2)
        with col3:
            st.markdown('<p class="field-label">📊 الأولوية</p>', unsafe_allow_html=True)
            priority = st.selectbox("الأولوية", ['عالية', 'متوسطة', 'منخفضة'], index=1, label_visibility="collapsed",
                                    help="عالية: أهداف ضرورية تحتاج تتحقق بأسرع وقت\nمتوسطة: أهداف مهمة لكن مو عاجلة\nمنخفضة: أهداف كمالية")
        with col4:
            st.markdown('<p class="field-label">⚡ هل الهدف ضروري؟</p>', unsafe_allow_html=True)
            essential = st.checkbox("هدف ضروري (مثل سيارة للعمل، علاج...)", value=False,
                                    help="الهدف الضروري يأخذ حصة أكبر من المدخرات")

        st.markdown('</div>', unsafe_allow_html=True)

    # عرض التوقعات
    if price and price > 0 and goal_name:
        temp_goals = st.session_state.goals + [{
            'goal_name': goal_name,
            'price': price,
            'saved_amount': 0,
            'priority': priority,
            'essential': essential,
            'completed': False
        }]
        distributions, emergency_amount, fun_money = calculate_smart_distribution(temp_goals, remaining)

        new_goal_dist = None
        for d in distributions:
            if d['goal_name'] == goal_name and d['price'] == price:
                new_goal_dist = d
                break

        if new_goal_dist:
            allocation = new_goal_dist['monthly_allocation']
            months = new_goal_dist['months_to_complete']
            progress = (0 / price) * 100

            st.markdown(f"""
            <div class="budget-box">
                <h3 style="margin: 0 0 15px 0; font-weight: 900;">📊 تحليل الهدف</h3>
                <div class="budget-breakdown">
                    <div class="budget-item">
                        <p style="color: #1B5E20; font-weight: 700; margin: 5px 0;">💵 شهرياً للهدف</p>
                        <p style="font-size: 1.8rem; font-weight: 900; color: #1B5E20;">{format_currency(allocation)}</p>
                        <p style="font-size: 0.75rem; color: #666;">ريال/شهر</p>
                    </div>
                    <div class="budget-item">
                        <p style="color: #E65100; font-weight: 700; margin: 5px 0;">⏱️ المدة المتوقعة</p>
                        <p style="font-size: 1.8rem; font-weight: 900; color: #E65100;">{format_timeline(months)}</p>
                    </div>
                    <div class="budget-item">
                        <p style="color: #8E24AA; font-weight: 700; margin: 5px 0;">📊 الأولوية</p>
                        <p style="font-size: 1.2rem; font-weight: 900; color: #8E24AA;">{priority}</p>
                        <p style="font-size: 0.75rem; color: #666;">{'⚡ ضروري' if essential else 'عادي'}</p>
                    </div>
                </div>
                {custom_progress_bar(0, "14px")}
                <p style="color: #444; font-size: 0.8rem; margin-top: 8px;">المبلغ موزع مع {len(st.session_state.goals)} أهداف أخرى | للطوارئ: {format_currency(emergency_amount)}</p>
            </div>
            """, unsafe_allow_html=True)

            if months > 24:
                st.markdown(f"""
                <div class="warning-card">
                    <p>💡 الهدف يحتاج {format_timeline(months)}</p>
                    <p style="font-size: 0.9rem;">نصائح لتسريع الهدف:</p>
                    <p style="font-size: 0.8rem;">• قلل المصاريف الشهرية مؤقتاً<br>• ابحث عن دخل إضافي (عمل جزئي، freelance)<br>• بيع أشياء غير مستخدمة</p>
                </div>
                """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 حفظ الهدف", use_container_width=True):
            if goal_name and price:
                new_goal = {
                    'goal_name': goal_name,
                    'price': price,
                    'saved_amount': 0,
                    'priority': priority,
                    'essential': essential,
                    'completed': False,
                    'created_date': datetime.now().strftime('%Y-%m-%d')
                }
                st.session_state.goals.append(new_goal)
                save_goals(st.session_state.goals)
                st.session_state.toast_message = f"✅ تم حفظ هدف '{goal_name}' بنجاح!"
                st.session_state.current_page = 'home'
                st.rerun()
            else:
                st.error("⚠️ الرجاء إدخال اسم الهدف وسعره")

    with col2:
        if st.button("← رجوع", use_container_width=True):
            st.session_state.current_page = 'home'
            st.rerun()


# ========== صفحة تفاصيل الهدف ==========
def show_results_page():
    if st.session_state.editing_goal is None or st.session_state.editing_goal >= len(st.session_state.goals):
        st.error("الهدف غير موجود")
        st.session_state.current_page = 'home'
        st.rerun()
        return

    data = st.session_state.goals[st.session_state.editing_goal]
    profile = st.session_state.profile

    if not profile or profile.get('monthly_income', 0) <= 0:
        st.warning("لا يوجد ملف شخصي")
        st.session_state.current_page = 'home'
        st.rerun()
        return

    monthly_income = profile['monthly_income']
    monthly_expenses = profile.get('essential_expenses', 0)
    remaining = monthly_income - monthly_expenses

    saved = data.get('saved_amount', 0)
    remaining_price = data['price'] - saved
    progress_pct = (saved / data['price'] * 100) if data['price'] > 0 else 0
    emoji = get_goal_emoji(data['goal_name'])
    priority = data.get('priority', 'متوسطة')
    essential = data.get('essential', False)
    priority_class, badge_class, badge_text = get_priority_color(priority, essential)
    completed = data.get('completed', False)

    # التوزيع
    distributions, emergency_amount, _ = calculate_smart_distribution(st.session_state.goals, remaining)
    goal_dist = None
    for d in distributions:
        if d['index'] == st.session_state.editing_goal:
            goal_dist = d
            break

    monthly_allocation = goal_dist['monthly_allocation'] if goal_dist else 0
    months_left = goal_dist['months_to_complete'] if goal_dist else 999

    st.markdown(
        f'{render_logo("small")}<h2 style="color: #0D3B0F; display: inline; margin-right: 10px; font-weight: 900;">تفاصيل الهدف</h2>',
        unsafe_allow_html=True)

    # إذا الهدف مكتمل
    if completed:
        st.markdown(f"""
        <div class="success-card" style="text-align: center; padding: 2rem;">
            <div style="font-size: 65px;">{emoji}</div>
            <h2 style="color: #0D3B0F !important; font-weight: 900; margin: 0.5rem 0;">{data['goal_name']}</h2>
            <p style="font-size: 1.3rem; font-weight: 700;">🎉 تم تحقيق الهدف بنجاح!</p>
            <p style="font-weight: 600;">💰 {format_currency(data['price'])} ريال</p>
            {f"<p style='font-size: 0.9rem; color: #666;'>تاريخ الإكمال: {data.get('completed_date', '')}</p>" if data.get('completed_date') else ""}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div style="text-align: center;"><div style="font-size: 65px;">{emoji}</div><h2 style="color: #0D3B0F; font-weight: 900;">{data["goal_name"]}</h2></div>',
            unsafe_allow_html=True)

        st.markdown(f"""
        <div class="highlight-card">
            <p style="color: white; font-weight: 600;">المتبقي للوصول لهدفك</p>
            <p style="font-size: 2.2rem; font-weight: 900; margin: 10px 0; color: white;">{format_currency(remaining_price)} ريال</p>
            {custom_progress_bar(progress_pct, "16px")}
            <p style="margin-top: 12px; color: white; font-weight: 700;">التقدم: {round(progress_pct, 1)}%</p>
            <p style="margin-top: 5px;"><span class="{badge_class}">{badge_text}</span></p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💰 سعر الهدف", f"{format_currency(data['price'])} ريال")
        with col2:
            st.metric("💵 المدخر", f"{format_currency(saved)} ريال")
        with col3:
            st.metric("📅 شهرياً للهدف", f"{format_currency(monthly_allocation)} ريال")

        st.markdown(f"""
        <div class="goal-card">
            <h3 style="text-align: center; font-weight: 800;">📊 خطة الإنجاز</h3>
            <div style="display: flex; justify-content: space-around; flex-wrap: wrap; margin: 1rem 0;">
                <div style="text-align: center;">
                    <p style="color: #666; font-size: 0.8rem;">💵 المتبقي</p>
                    <p style="font-size: 1.3rem; font-weight: 900; color: #B71C1C;">{format_currency(remaining_price)}</p>
                </div>
                <div style="text-align: center;">
                    <p style="color: #666; font-size: 0.8rem;">⏱️ المدة</p>
                    <p style="font-size: 1.3rem; font-weight: 900; color: #E65100;">{format_timeline(months_left)}</p>
                </div>
                <div style="text-align: center;">
                    <p style="color: #666; font-size: 0.8rem;">🛡️ طوارئ شهري</p>
                    <p style="font-size: 1.3rem; font-weight: 900; color: #8E24AA;">{format_currency(emergency_amount)}</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # حالة الهدف
        if months_left <= 3:
            st.markdown('<div class="status-success">✅ ممتاز! هدفك قريب جداً - أقل من 3 شهور</div>',
                        unsafe_allow_html=True)
        elif months_left <= 12:
            st.markdown('<div class="status-warning">⚠️ جيد - هدفك خلال سنة تقريباً</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="status-danger">🔴 الهدف بعيد ({format_timeline(months_left)}) - فكر في مصادر دخل إضافية</div>',
                unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if not completed and st.button("💰 إيداع", use_container_width=True):
            st.session_state.current_page = 'deposit'
            st.rerun()
    with col2:
        if st.button("← العودة", use_container_width=True):
            st.session_state.editing_goal = None
            st.session_state.current_page = 'home'
            st.rerun()


# ========== صفحة إيداع ==========
def show_deposit_page():
    if st.session_state.editing_goal is None or not st.session_state.goals or st.session_state.editing_goal >= len(
            st.session_state.goals):
        st.error("⚠️ الهدف غير موجود")
        st.session_state.current_page = 'home'
        st.rerun()
        return

    data = st.session_state.goals[st.session_state.editing_goal]
    saved = data.get('saved_amount', 0)
    remaining = data['price'] - saved
    completed = data.get('completed', False)

    if completed or remaining <= 0:
        emoji = get_goal_emoji(data['goal_name'])
        show_celebration(data['goal_name'], emoji)
        st.success(f"🎉 مبروك! لقد حققت هدف '{data['goal_name']}' بالكامل!")
        if st.button("← العودة للرئيسية"):
            st.session_state.current_page = 'home'
            st.rerun()
        return

    progress_pct = (saved / data['price'] * 100) if data['price'] > 0 else 0
    emoji = get_goal_emoji(data['goal_name'])

    st.markdown(
        f'{render_logo("small")}<h2 style="color: #0D3B0F; display: inline; margin-right: 10px; font-weight: 900;">إيداع في الهدف</h2>',
        unsafe_allow_html=True)
    st.markdown(
        f'<div class="goal-card" style="text-align: center;"><span style="font-size: 50px;">{emoji}</span><h3 style="color: #0D3B0F; margin: 0.5rem 0; font-weight: 800;">{data["goal_name"]}</h3></div>',
        unsafe_allow_html=True)

    st.markdown(f"""
    <div style="display: flex; justify-content: center; margin: 1rem 0;">
        <div class="balance-circle">
            <div style="text-align: center;">
                <p style="color: white; font-size: 0.8rem; margin: 0; font-weight: 600;">المدخر</p>
                <p style="color: white; font-size: 1.4rem; font-weight: 900; margin: 0;">{format_currency(saved)}</p>
                <p style="color: white; font-size: 0.75rem; margin: 0;">ريال</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div style="margin: 1rem 0;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
            <span style="color: #444444; font-weight: 600;">التقدم</span>
            <span style="color: #0D3B0F; font-weight: 800;">{round(progress_pct, 1)}%</span>
        </div>
        {custom_progress_bar(progress_pct)}
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("💰 الهدف", f"{format_currency(data['price'])} ريال")
    with col2:
        st.metric("🎯 المتبقي", f"{format_currency(remaining)} ريال")

    st.markdown('<div class="goal-card">', unsafe_allow_html=True)
    st.markdown('<p class="field-label">💵 المبلغ المراد إيداعه (ريال)</p>', unsafe_allow_html=True)
    deposit_amount = st.number_input("مبلغ_الإيداع", min_value=1, max_value=int(remaining), step=50, value=None,
                                     placeholder="أدخل المبلغ...", label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("💰 تأكيد الإيداع", use_container_width=True):
            if deposit_amount and deposit_amount > 0:
                if update_saved_amount(st.session_state.editing_goal, deposit_amount):
                    new_saved = st.session_state.goals[st.session_state.editing_goal].get('saved_amount', 0)
                    if new_saved >= data['price']:
                        # الهدف اكتمل - راح يظهر الاحتفال في الصفحة الرئيسية
                        st.session_state.toast_message = f"🎉 مبروك! حققت هدف '{data['goal_name']}'!"
                        st.session_state.current_page = 'home'
                        st.rerun()
                    else:
                        st.session_state.toast_message = f"✅ تم إيداع {format_currency(deposit_amount)} ريال بنجاح!"
                        st.session_state.current_page = 'home'
                        st.rerun()
                else:
                    st.error("⚠️ حدث خطأ")
            else:
                st.error("⚠️ الرجاء إدخال مبلغ صحيح")

    with col2:
        if st.button("← رجوع", use_container_width=True):
            st.session_state.editing_goal = None
            st.session_state.current_page = 'home'
            st.rerun()


# ========== محاكاة الأزمات الواقعية ==========
def show_simulator_page():
    st.markdown(
        f'{render_logo("small")}<h2 style="color: #0D3B0F; display: inline; margin-right: 10px; font-weight: 900;">محاكاة أزمة مالية</h2>',
        unsafe_allow_html=True)
    st.markdown('<p style="color: #444444; font-weight: 500;">اختبر تأثير الأزمات المالية الواقعية على أهدافك</p>',
                unsafe_allow_html=True)

    profile = st.session_state.profile

    if not profile or profile.get('monthly_income', 0) <= 0:
        st.warning("يجب إعداد ملفك الشخصي أولاً")
        if st.button("👤 إعداد الملف الشخصي"):
            st.session_state.current_page = 'profile'
            st.rerun()
        return

    monthly_income = profile['monthly_income']
    monthly_expenses = profile.get('essential_expenses', 0)
    remaining = monthly_income - monthly_expenses
    distributions, emergency_amount, _ = calculate_smart_distribution(st.session_state.goals, remaining)
    total_monthly_savings = sum(d['monthly_allocation'] for d in distributions)

    # عرض الأزمات الواقعية
    st.markdown('<h3 style="color: #0D3B0F; text-align: center; margin: 1rem 0;">⚠️ اختر سيناريو الأزمة</h3>',
                unsafe_allow_html=True)

    crisis_cols = st.columns(3)
    selected_crisis = None

    crisis_names = list(REALISTIC_CRISES.keys())
    for i, (name, crisis) in enumerate(REALISTIC_CRISES.items()):
        col_idx = i % 3
        with crisis_cols[col_idx]:
            impact_text = crisis['impact'].replace('{}', f"{crisis['min_cost']:,} - {crisis['max_cost']:,}")
            st.markdown(f"""
            <div class="crisis-card" style="text-align: center; cursor: pointer;">
                <div style="font-size: 45px;">{crisis['icon']}</div>
                <h4 style="color: #B71C1C; margin: 8px 0; font-weight: 800;">{name}</h4>
                <p style="font-size: 0.8rem; color: #666;">{crisis['description']}</p>
                <p style="font-size: 0.8rem; font-weight: 700; color: #E65100;">التكلفة: {crisis['min_cost']:,} - {crisis['max_cost']:,} ريال</p>
            </div>
            """, unsafe_allow_html=True)

            if st.button(f"⚡ محاكاة: {name}", key=f"crisis_{i}", use_container_width=True):
                selected_crisis = name
                st.session_state.selected_crisis = name

    # خيار إدخال مبلغ مخصص
    st.markdown('<div class="goal-card">', unsafe_allow_html=True)
    st.markdown('<p class="field-label">💸 أو أدخل مبلغ مخصص للمحاكاة</p>', unsafe_allow_html=True)
    custom_amount = st.number_input("مبلغ_مخصص", min_value=0, max_value=1000000, step=500, value=None,
                                    placeholder="أدخل مبلغ مخصص...", label_visibility="collapsed")
    if custom_amount and custom_amount > 0:
        if st.button("⚡ محاكاة بالمبلغ المخصص", use_container_width=True):
            selected_crisis = None
            st.session_state.custom_crisis_amount = custom_amount
    st.markdown('</div>', unsafe_allow_html=True)

    # تنفيذ المحاكاة
    crisis_to_simulate = selected_crisis or st.session_state.get('selected_crisis')
    crisis_amount = st.session_state.get('custom_crisis_amount')

    if crisis_to_simulate and crisis_to_simulate in REALISTIC_CRISES:
        crisis = REALISTIC_CRISES[crisis_to_simulate]
        # نستخدم متوسط التكلفة
        crisis_amount = (crisis['min_cost'] + crisis['max_cost']) // 2

    if crisis_amount and crisis_amount > 0:
        st.markdown(f"""
        <div class="danger-card">
            <p style="font-size: 1.3rem;">⚠️ نتيجة المحاكاة</p>
            <p style="font-weight: 600;">مبلغ الأزمة: <strong>{format_currency(crisis_amount)} ريال</strong></p>
        </div>
        """, unsafe_allow_html=True)

        # التأثير على الأهداف
        if distributions and total_monthly_savings > 0:
            delay_months = crisis_amount / total_monthly_savings

            st.markdown(f"""
            <div class="warning-card">
                <p>⏱️ تأخير جميع الأهداف: <strong>{format_timeline(delay_months)}</strong></p>
                <p style="font-size: 0.9rem;">بمعدل ادخار {format_currency(total_monthly_savings)} ريال/شهر</p>
            </div>
            """, unsafe_allow_html=True)

            # تأثير على كل هدف
            st.markdown('<h4 style="text-align: center; margin: 1rem 0;">📊 التأثير على كل هدف</h4>',
                        unsafe_allow_html=True)
            for d in distributions:
                emoji = get_goal_emoji(d['goal_name'])
                new_months = d['months_to_complete'] + delay_months
                additional_savings_needed = delay_months * d['monthly_allocation']

                st.markdown(f"""
                <div class="distribution-card">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 30px;">{emoji}</span>
                        <div style="flex: 1;">
                            <strong>{d['goal_name']}</strong>
                            <p style="margin: 3px 0; font-size: 0.85rem; color: #666;">
                                المدة الأصلية: {format_timeline(d['months_to_complete'])} 
                                → <span style="color: #B71C1C; font-weight: 700;">الجديدة: {format_timeline(new_months)}</span>
                            </p>
                            <p style="margin: 0; font-size: 0.8rem; color: #E65100;">
                                تكلفة إضافية: {format_currency(additional_savings_needed)} ريال
                            </p>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # نصائح للتعامل مع الأزمة
            if crisis_to_simulate and crisis_to_simulate in REALISTIC_CRISES:
                crisis_info = REALISTIC_CRISES[crisis_to_simulate]
                st.markdown(f"""
                <div class="tip-card" style="border-right-color: #FF9800; border-right-width: 5px;">
                    <h3>💡 نصيحة للتعامل مع هذه الأزمة</h3>
                    <p>{crisis_info['advice']}</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("لا توجد أهداف نشطة لتحليل التأثير عليها")

    # إعادة تعيين
    if 'selected_crisis' in st.session_state:
        del st.session_state.selected_crisis
    if 'custom_crisis_amount' in st.session_state:
        del st.session_state.custom_crisis_amount

    if st.button("← العودة للرئيسية", use_container_width=True):
        st.session_state.editing_goal = None
        st.session_state.current_page = 'home'
        st.rerun()


# ========== صفحة النصائح ==========
def show_tips_page():
    st.markdown("""
    <div class="tips-header">
        <div style="font-size: 60px;">💡</div>
        <h2 style="color: #0D3B0F;">نصائح ذكية للادخار</h2>
        <p style="color: #444444; font-weight: 500; margin-top: 8px;">نصائح عملية تساعدك على توفير المال وتحقيق أهدافك بشكل أسرع</p>
    </div>
    """, unsafe_allow_html=True)

    tips = [
        ('🍳', 'الطهي المنزلي', 'يوفر حتى 60% من مصاريف الأكل مقارنة بالمطاعم والتوصيل', 'توفير 400-800 ريال شهرياً'),
        ('☕', 'القهوة في المنزل', 'تحضير القهوة منزلياً بدلاً من شرائها يومياً من الكافيهات',
         'توفير 200-500 ريال شهرياً'),
        (
        '📱', 'مراجعة الاشتراكات', 'إلغاء الاشتراكات الرقمية غير المستخدمة وتقليل الباقات', 'توفير 100-300 ريال شهرياً'),
        ('🚗', 'المشاركة في المواصلات', 'تقليل استهلاك الوقود وصيانة السيارة بالمشاركة', 'توفير 200-400 ريال شهرياً'),
        ('💰', 'قاعدة 50/30/20', '50% للضروريات، 30% للكماليات، 20% للادخار والاستثمار', 'ادخار منتظم ومضمون'),
        ('🏦', 'حساب توفير منفصل', 'حول مبلغ الادخار تلقائياً أول كل شهر لحساب منفصل', 'التزام تلقائي بالادخار'),
        ('🛒', 'قائمة التسوق الذكية', 'اكتب قائمة مشتريات قبل الذهاب للسوق والتزم بها تماماً',
         'توفير 300-600 ريال شهرياً'),
        ('💡', 'ترشيد استهلاك الطاقة', 'إطفاء الأجهزة غير المستخدمة واستخدام لمبات LED', 'توفير 100-250 ريال شهرياً'),
        ('📊', 'تتبع المصروفات اليومية', 'سجل كل مصروفاتك لتكتشف أين تذهب أموالك', 'اكتشاف 500-1000 ريال مصاريف مخفية'),
        ('🎯', 'تحدي الـ 30 يوم', 'تجنب المصاريف غير الضرورية لمدة 30 يوماً متواصلة', 'توفير 500-1500 ريال في شهر')
    ]

    for emoji, title, desc, saving in tips:
        st.markdown(f"""
        <div class="tip-card">
            <div style="display: flex; align-items: center; gap: 15px; flex-wrap: wrap;">
                <div style="font-size: 45px; min-width: 55px; text-align: center;">{emoji}</div>
                <div style="flex: 1; min-width: 200px;">
                    <h3 style="margin: 0 0 5px 0;">{title}</h3>
                    <p style="margin: 0 0 8px 0;">{desc}</p>
                    <span class="tip-badge">💚 {saving}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<br>', unsafe_allow_html=True)

    if st.button("← العودة", use_container_width=True):
        if st.session_state.editing_goal is not None:
            st.session_state.current_page = 'results'
        else:
            st.session_state.current_page = 'home'
        st.rerun()


# ========== التوجيه الرئيسي ==========
def main():
    pages = {
        'home': show_home_page,
        'profile': show_profile_page,
        'add_goal': show_add_goal_page,
        'deposit': show_deposit_page,
        'results': show_results_page,
        'simulator': show_simulator_page,
        'tips': show_tips_page,
    }

    current = st.session_state.current_page
    if current in pages:
        pages[current]()
    else:
        show_home_page()


if __name__ == "__main__":
    # تحقق من الأهداف المكتملة عند بدء التشغيل
    if 'goals' in st.session_state:
        current_completed = len([g for g in st.session_state.goals if g.get('completed')])
        if current_completed > st.session_state.last_goals_count:
            # فيه هدف جديد اكتمل
            pass  # سيتم التعامل معه في show_home_page
        st.session_state.last_goals_count = current_completed

    main()