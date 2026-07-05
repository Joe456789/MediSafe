let currentImageBase64 = null;
let currentMimeType = null;
let currentLang = 'en';
let currentIngredient = "";
let currentReportMarkdown = "";
let lastCheckedIngredient = "";

// Pediatric dosage calculator config
let activeDosePerKgMin = 10;
let activeDosePerKgMax = 15;
let doseUnit = "mg";

// TTS Speech Synthesis State
let synth = window.speechSynthesis;
let utterance = null;
let isSpeaking = false;

// DOM Elements
const imageInput = document.getElementById('imageInput');
const uploadBtn = document.getElementById('uploadBtn');
const imagePreviewContainer = document.getElementById('imagePreviewContainer');
const imagePreview = document.getElementById('imagePreview');
const clearImageBtn = document.getElementById('clearImageBtn');

const langEn = document.getElementById('langEn');
const langZh = document.getElementById('langZh');

const analyzeBtn = document.getElementById('analyzeBtn');
const ingredientInput = document.getElementById('ingredientInput');

const safetyBadge = document.getElementById('safetyBadge');
const resultIngredient = document.getElementById('resultIngredient');
const cssPill = document.getElementById('cssPill');
const pillLabel = document.getElementById('pillLabel');

const alcoholStatus = document.querySelector('#food-alcohol .food-status');
const dairyStatus = document.querySelector('#food-dairy .food-status');
const grapefruitStatus = document.querySelector('#food-grapefruit .food-status');
const caffeineStatus = document.querySelector('#food-caffeine .food-status');

const speakBtn = document.getElementById('speakBtn');
const reportContent = document.getElementById('reportContent');

const weightRange = document.getElementById('weightRange');
const weightDisplay = document.getElementById('weightDisplay');
const calculatedDose = document.getElementById('calculatedDose');

const reminderBtn = document.getElementById('reminderBtn');
const pdfBtn = document.getElementById('pdfBtn');

const chatHistory = document.getElementById('chatHistory');
const chatInput = document.getElementById('chatInput');
const sendChatBtn = document.getElementById('sendChatBtn');

const triagePanel = document.getElementById('triagePanel');
const triageWarningText = document.getElementById('triageWarningText');
const triageApproveBtn = document.getElementById('triageApproveBtn');
const triageCancelBtn = document.querySelector('.cancel-btn-triage');

// Image upload handling
uploadBtn.addEventListener('click', () => {
    imageInput.click();
});

imageInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = (event) => {
            const result = event.target.result;
            imagePreview.src = result;
            imagePreviewContainer.classList.remove('hidden');
            ingredientInput.value = "";
            applyPhotoPlaceholder();
            ingredientInput.disabled = true;
            
            const parts = result.split(',');
            currentMimeType = parts[0].match(/:(.*?);/)[1];
            currentImageBase64 = parts[1];
        };
        reader.readAsDataURL(file);
    }
});

clearImageBtn.addEventListener('click', () => {
    imageInput.value = "";
    currentImageBase64 = null;
    currentMimeType = null;
    imagePreviewContainer.classList.add('hidden');
    ingredientInput.disabled = false;
    applyInputPlaceholder();
});

function applyPhotoPlaceholder() {
    ingredientInput.placeholder = currentLang === 'zh' 
        ? "照片已附加！將優先進行 OCR 辨識..." 
        : "Photo attached! OCR will run first...";
}

function applyInputPlaceholder() {
    ingredientInput.placeholder = currentLang === 'zh'
        ? "輸入藥物名稱或活性成分 (例如 Acetaminophen, Tylenol)..."
        : "Enter a medicine name or active ingredient (e.g. Acetaminophen, Tylenol)...";
}

// Localization Dictionary
const localization = {
    en: {
        subtitle: "Your plain-English medicine safety translator",
        analyzeBtn: "Analyze Safety",
        trendingHeader: "Trending Safety Checks",
        foodHeader: "Food & Drink Interactions",
        foodAlcohol: "Alcohol",
        foodDairy: "Dairy",
        foodGrapefruit: "Grapefruit",
        foodCaffeine: "Caffeine",
        reportHeader: "AI Safety Translation",
        speakBtn: "🔊 Speak",
        speakBtnActive: "🛑 Stop",
        calcHeader: "👶 Pediatric Dosage Calculator",
        calcDesc: "Estimate child dosage based on weight. (Consult a doctor before administering!)",
        weightLabel: "Child's Weight (kg):",
        reminderBtn: "⏰ Get Dose Reminder",
        pdfBtn: "📄 Save as PDF",
        rawSummary: "View Raw Database Findings (Data Fetcher Agent)",
        chatHeader: "💬 Have questions? Ask AI Pharmacist",
        chatPlaceholder: "Can I take this with milk? What if I miss a dose?...",
        chatSend: "Ask",
        chatBotGreeting: "Hi! I'm your AI pharmacist. Ask me anything about this medicine.",
        pharmacistDisclaimer: "Always consult a doctor or pharmacist for serious health concerns.",
        calcResultPrefix: "Estimated Safe Dose: ",
        calcResultSuffix: " per dose.",
        pillNote: "*Representative model. Actual appearance may vary."
    },
    zh: {
        subtitle: "您的中英文藥物安全翻譯官",
        analyzeBtn: "安全分析",
        trendingHeader: "熱門安全檢查",
        foodHeader: "食物與飲料交互作用",
        foodAlcohol: "酒精",
        foodDairy: "乳製品",
        foodGrapefruit: "葡萄柚",
        foodCaffeine: "咖啡因",
        reportHeader: "AI 安全導讀",
        speakBtn: "🔊 語音朗讀",
        speakBtnActive: "🛑 停止",
        calcHeader: "👶 兒童用藥劑量計算器",
        calcDesc: "根據體重預估兒童劑量。（服用前請務必諮詢醫生！）",
        weightLabel: "兒童體重 (kg)：",
        reminderBtn: "⏰ 取得服藥提醒",
        pdfBtn: "📄 儲存為 PDF",
        rawSummary: "查看原始資料庫查詢結果 (資料搜集 Agent)",
        chatHeader: "💬 還有其他問題？詢問 AI 藥劑師",
        chatPlaceholder: "我可以配牛奶吃嗎？如果漏吃了一劑該怎麼辦？...",
        chatSend: "送出",
        chatBotGreeting: "嗨！我是您的 AI 藥劑師。有任何關於此藥物的問題都可以問我。",
        pharmacistDisclaimer: "如有嚴重的健康問題，請務必諮詢醫生或藥劑師。",
        calcResultPrefix: "預估安全劑量：每劑 ",
        calcResultSuffix: "。",
        pillNote: "*此為常見外觀示意圖，實際藥物形狀與顏色可能因藥廠而異。"
    }
};

function applyLocalization(lang) {
    const l = localization[lang];
    document.querySelector('header p').innerText = l.subtitle;
    analyzeBtn.innerText = l.analyzeBtn;
    document.querySelector('.trending-container h3').innerText = l.trendingHeader;
    document.querySelector('.food-warnings-section h3').innerText = l.foodHeader;
    
    document.querySelector('#food-alcohol .food-name').innerText = l.foodAlcohol;
    document.querySelector('#food-dairy .food-name').innerText = l.foodDairy;
    document.querySelector('#food-grapefruit .food-name').innerText = l.foodGrapefruit;
    document.querySelector('#food-caffeine .food-name').innerText = l.foodCaffeine;
    
    document.querySelector('.report-header h3').innerText = l.reportHeader;
    if (!isSpeaking) {
        speakBtn.innerText = l.speakBtn;
    } else {
        speakBtn.innerText = l.speakBtnActive;
    }
    
    document.querySelector('.dosage-calculator-section h3').innerText = l.calcHeader;
    document.querySelector('.calc-description').innerText = l.calcDesc;
    document.querySelector('.calc-controls label').innerText = l.weightLabel;
    
    reminderBtn.innerText = l.reminderBtn;
    pdfBtn.innerText = l.pdfBtn;
    document.querySelector('.raw-data-section summary').innerText = l.rawSummary;
    
    document.querySelector('.chat-section h3').innerText = l.chatHeader;
    chatInput.placeholder = l.chatPlaceholder;
    sendChatBtn.innerText = l.chatSend;
    
    // Set pill note text
    document.getElementById('pillNote').innerText = l.pillNote;
    
    if (currentImageBase64) {
        applyPhotoPlaceholder();
    } else {
        applyInputPlaceholder();
    }
}

// Language Switch Event Listeners
langEn.addEventListener('click', () => {
    if (currentLang === 'en') return;
    currentLang = 'en';
    langEn.classList.add('active');
    langZh.classList.remove('active');
    applyLocalization('en');
    
    // If there is an active search, re-run analysis in English
    if (currentIngredient) {
        runAnalysis(currentIngredient, false);
    }
});

langZh.addEventListener('click', () => {
    if (currentLang === 'zh') return;
    currentLang = 'zh';
    langZh.classList.add('active');
    langEn.classList.remove('active');
    applyLocalization('zh');
    
    // If there is an active search, re-run analysis in Chinese
    if (currentIngredient) {
        runAnalysis(currentIngredient, false);
    }
});

// Helper dictionaries for pill translation
function translateColor(color, lang) {
    if (lang !== 'zh') {
        if (color.toLowerCase() === 'red-yellow') return 'Red/Yellow';
        return color.charAt(0).toUpperCase() + color.slice(1);
    }
    const mapping = {
        white: '白色',
        red: '紅色',
        orange: '橘色',
        blue: '藍色',
        yellow: '黃色',
        brown: '棕色',
        'red-yellow': '紅黃相間'
    };
    return mapping[color.toLowerCase()] || color;
}

function translateType(type, lang) {
    if (lang !== 'zh') return type.charAt(0).toUpperCase() + type.slice(1);
    const mapping = {
        tablet: '藥片',
        capsule: '膠囊',
        liquid: '藥水'
    };
    return mapping[type.toLowerCase()] || type;
}

function updateFoodWarning(element, status, lang) {
    element.className = 'food-status ' + status;
    if (status === 'safe') {
        element.innerText = lang === 'zh' ? '安全' : 'Safe';
    } else {
        element.innerText = lang === 'zh' ? '避免' : 'Avoid';
    }
}

// Configure calculator dosage based on medicine
function updateDoseCalculatorConfig(ingredient) {
    const name = ingredient.toLowerCase();
    if (name.includes('acetaminophen') || name.includes('paracetamol') || name.includes('tylenol')) {
        activeDosePerKgMin = 10;
        activeDosePerKgMax = 15;
        doseUnit = "mg";
    } else if (name.includes('ibuprofen') || name.includes('advil') || name.includes('motrin')) {
        activeDosePerKgMin = 5;
        activeDosePerKgMax = 10;
        doseUnit = "mg";
    } else if (name.includes('calcium carbonate') || name.includes('antacid') || name.includes('mylanta') || name.includes('tums')) {
        activeDosePerKgMin = 10;
        activeDosePerKgMax = 20;
        doseUnit = "mg";
    } else {
        // Safe default dosage limits
        activeDosePerKgMin = 10;
        activeDosePerKgMax = 15;
        doseUnit = "mg";
    }
}

function updateCalculatedDose() {
    const weight = parseInt(weightRange.value, 10);
    weightDisplay.innerText = `${weight} kg`;
    
    const minDose = weight * activeDosePerKgMin;
    const maxDose = weight * activeDosePerKgMax;
    
    const l = localization[currentLang];
    calculatedDose.innerHTML = `${minDose}${doseUnit} - ${maxDose}${doseUnit}`;
}

weightRange.addEventListener('input', updateCalculatedDose);

// Reset Chatbox to localized initial state
function resetChatHistory() {
    chatHistory.innerHTML = "";
    const botMsg = document.createElement('div');
    botMsg.className = 'chat-message bot-message';
    botMsg.innerText = localization[currentLang].chatBotGreeting;
    chatHistory.appendChild(botMsg);
}

// Strip markdown tags to read text cleanly
function cleanMarkdownForTTS(text) {
    return text
        .replace(/[#*`_-]/g, '') // remove markdown notation characters
        .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // replace markdown links with title only
        .trim();
}

// Stop speaking function
function stopSpeaking() {
    if (synth.speaking) {
        synth.cancel();
    }
    isSpeaking = false;
    speakBtn.innerText = localization[currentLang].speakBtn;
}

// Speak button listener
speakBtn.addEventListener('click', () => {
    if (isSpeaking) {
        stopSpeaking();
        return;
    }
    
    if (!currentReportMarkdown) return;
    
    const cleanedText = cleanMarkdownForTTS(currentReportMarkdown);
    utterance = new SpeechSynthesisUtterance(cleanedText);
    
    // Choose appropriate voice/lang
    if (currentLang === 'zh') {
        utterance.lang = 'zh-TW';
    } else {
        utterance.lang = 'en-US';
    }
    
    utterance.onend = () => {
        isSpeaking = false;
        speakBtn.innerText = localization[currentLang].speakBtn;
    };
    
    utterance.onerror = () => {
        isSpeaking = false;
        speakBtn.innerText = localization[currentLang].speakBtn;
    };
    
    isSpeaking = true;
    speakBtn.innerText = localization[currentLang].speakBtnActive;
    synth.speak(utterance);
});

// Run safety analysis
async function runAnalysis(input, bypassTriage = false) {
    const loader = document.getElementById('loader');
    const resultPanel = document.getElementById('result');
    const errorPanel = document.getElementById('error');
    const loaderText = document.getElementById('loaderText');
    
    // UI Reset
    resultPanel.classList.add('hidden');
    errorPanel.classList.add('hidden');
    triagePanel.classList.add('hidden');
    stopSpeaking();
    resetChatHistory();
    
    if (currentImageBase64) {
        loaderText.innerText = currentLang === 'zh'
            ? "正在運行 Vision OCR 辨識照片，隨後將檢索 FDA/PubMed 數據..."
            : "Running Vision OCR to extract medicine name, then gathering FDA/PubMed data...";
    } else {
        loaderText.innerText = currentLang === 'zh'
            ? "AI Agent 正在從 FDA、PubMed 與臨床試驗庫中蒐集數據..."
            : "Agents are gathering data from FDA, PubMed, and Clinical Trials...";
    }
    loader.classList.remove('hidden');
    
    try {
        const payload = {
            ingredient: input,
            image_base64: currentImageBase64,
            mime_type: currentMimeType,
            bypass_triage: bypassTriage,
            lang: currentLang
        };

        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to fetch analysis');
        }

        // Check if HITL Triage is required (MCP allergy conflict)
        if (data.status === "requires_triage") {
            loader.classList.add('hidden');
            
            const patientName = data.patient_name;
            const ingredientName = data.ingredient;
            const allergyList = data.allergies.join(", ");
            
            if (currentLang === 'zh') {
                triageWarningText.innerHTML = `<strong>⚠️ 警告：</strong> 病患 <strong>${patientName}</strong> 對 <strong>${ingredientName}</strong> 有過敏史記錄！<br><br>從 User Profile MCP 伺服器獲取的過敏記錄：<strong>${allergyList}</strong>。<br><br>請確認是否需要手動覆寫此項安全警報（醫療專家 Human-in-the-Loop 安全決策）。`;
                document.getElementById('triageApproveBtn').innerText = "覆寫並強制分析（藥劑師確認）";
                document.querySelector('.cancel-btn-triage').innerText = "取消分析";
                document.querySelector('.triage-header h2').innerText = "關鍵過敏警報 (HITL 覆寫機制)";
            } else {
                triageWarningText.innerHTML = `<strong>WARNING:</strong> Patient <strong>${patientName}</strong> has a documented allergy to <strong>${ingredientName}</strong>!<br><br>Allergic history retrieved from User Profile MCP: <strong>${allergyList}</strong>.<br><br>Please confirm if you want to override this safety alert (Human-in-the-Loop Triage).`;
                document.getElementById('triageApproveBtn').innerText = "Approve & Override (Pharmacist)";
                document.querySelector('.cancel-btn-triage').innerText = "Cancel";
                document.querySelector('.triage-header h2').innerText = "Critical Allergy Alert (HITL Triage)";
            }
            
            lastCheckedIngredient = data.ingredient;
            triagePanel.classList.remove('hidden');
            return;
        }

        // Set global variables for Chat and TTS
        currentIngredient = data.extracted_ingredient || data.ingredient;
        currentReportMarkdown = data.report;
        
        // Populate UI Title & Info
        resultIngredient.innerText = currentIngredient;
        reportContent.innerHTML = marked.parse(data.report);
        document.getElementById('disclaimerText').innerText = data.disclaimer;
        
        // Safety badge setup
        safetyBadge.className = 'safety-badge ' + data.safety_level;
        if (data.safety_level === 'safe') {
            safetyBadge.innerText = currentLang === 'zh' ? '🟢 安全' : '🟢 SAFE';
        } else if (data.safety_level === 'warning') {
            safetyBadge.innerText = currentLang === 'zh' ? '🟡 警告' : '🟡 WARNING';
        } else {
            safetyBadge.innerText = currentLang === 'zh' ? '🔴 危險 / 回收' : '🔴 DANGER / RECALL';
        }

        // 3D Pill Visualizer styling & colors
        const colorPalette = {
            white: '#ffffff',
            red: '#ef4444',
            orange: '#f97316',
            blue: '#3b82f6',
            yellow: '#eab308',
            brown: '#78350f'
        };
        const typeStr = data.pill_type.toLowerCase();
        const colorStr = data.pill_color.toLowerCase();
        
        cssPill.className = 'css-pill ' + typeStr;
        cssPill.style.background = ''; // Clear default style inline
        
        if (typeStr === 'capsule') {
            if (colorStr === 'red-yellow') {
                cssPill.style.background = 'linear-gradient(to right, #ef4444 50%, #eab308 50%)';
            } else {
                const activeColorHex = colorPalette[colorStr] || '#ffffff';
                cssPill.style.background = `linear-gradient(to right, ${activeColorHex} 50%, #ffffff 50%)`;
            }
        } else if (typeStr === 'tablet') {
            if (colorStr === 'red-yellow') {
                cssPill.style.background = 'linear-gradient(to right, #ef4444 50%, #eab308 50%)';
            } else {
                cssPill.style.background = colorPalette[colorStr] || '#ffffff';
            }
        } else if (typeStr === 'liquid') {
            if (colorStr === 'red-yellow') {
                cssPill.style.background = 'linear-gradient(to right, #ef4444 50%, #eab308 50%)';
            } else {
                cssPill.style.background = colorPalette[colorStr] || '#3b82f6';
            }
        }
        
        pillLabel.innerText = `${translateColor(data.pill_color, currentLang)} ${translateType(data.pill_type, currentLang)}`;

        // Populate Food Warnings
        const warnings = data.food_warnings || {};
        updateFoodWarning(alcoholStatus, warnings.alcohol || 'safe', currentLang);
        updateFoodWarning(dairyStatus, warnings.dairy || 'safe', currentLang);
        updateFoodWarning(grapefruitStatus, warnings.grapefruit || 'safe', currentLang);
        updateFoodWarning(caffeineStatus, warnings.caffeine || 'safe', currentLang);

        // Generate and display actionable food warnings text
        let detailHtml = [];
        if (warnings.alcohol === 'avoid') {
            detailHtml.push(currentLang === 'zh' 
                ? "🍷 <strong>酒精</strong>：請避免飲酒，酒精可能會加重藥物副作用，增加肝臟或胃部負擔。" 
                : "🍷 <strong>Alcohol</strong>: Avoid alcohol as it may worsen drug side effects or increase liver/stomach strain.");
        }
        if (warnings.dairy === 'avoid') {
            detailHtml.push(currentLang === 'zh' 
                ? "🥛 <strong>乳製品</strong>：請勿配牛奶或乳製品服用，鈣質可能會與藥物結合，降低吸收效果。" 
                : "🥛 <strong>Dairy</strong>: Avoid taking with milk or dairy as calcium can bind to the drug and reduce absorption.");
        }
        if (warnings.grapefruit === 'avoid') {
            detailHtml.push(currentLang === 'zh' 
                ? "🍇 <strong>葡萄柚</strong>：請避免食用葡萄柚，它會干擾藥物在肝臟的代謝，使體內藥物濃度過高。" 
                : "🍇 <strong>Grapefruit</strong>: Avoid grapefruit as it interferes with drug metabolism, raising drug levels in blood.");
        }
        if (warnings.caffeine === 'avoid') {
            detailHtml.push(currentLang === 'zh' 
                ? "☕ <strong>咖啡因</strong>：請限制茶或咖啡，咖啡因可能加重藥物刺激或引起心悸與失眠。" 
                : "☕ <strong>Caffeine</strong>: Limit coffee/tea as caffeine may worsen drug irritation, palpitations, or insomnia.");
        }
        if (detailHtml.length === 0) {
            detailHtml.push(currentLang === 'zh'
                ? "🟢 本藥物與上述常見食物、飲料無重大已知交互作用，但建議服用時仍以開水為主。"
                : "🟢 No major known interactions with the listed food/drinks. Always take with plain water.");
        }
        document.getElementById('foodWarningDetail').innerHTML = detailHtml.join("<br><br>");

        // Update Child Calculator Config
        updateDoseCalculatorConfig(currentIngredient);
        updateCalculatedDose();

        // Populate Raw Findings
        const rawJson = JSON.stringify(data.raw_data, null, 2);
        document.getElementById('rawDataContent').innerText = rawJson;
        
        // Show panel
        loader.classList.add('hidden');
        resultPanel.classList.remove('hidden');

    } catch (err) {
        loader.classList.add('hidden');
        document.getElementById('errorText').innerText = err.message;
        errorPanel.classList.remove('hidden');
    }
}

analyzeBtn.addEventListener('click', () => {
    const input = ingredientInput.value.trim();
    if (!input && !currentImageBase64) return;
    runAnalysis(input, false);
});

triageApproveBtn.addEventListener('click', () => {
    runAnalysis(lastCheckedIngredient, true);
});

triageCancelBtn.addEventListener('click', () => {
    triagePanel.classList.add('hidden');
    if (currentImageBase64) {
        clearImageBtn.click();
    }
});

// Input text enter trigger
ingredientInput.addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
        analyzeBtn.click();
    }
});

// Trending glassmorphism card buttons click event
document.querySelectorAll('.med-card').forEach(card => {
    card.addEventListener('click', () => {
        const med = card.getAttribute('data-med');
        if (currentImageBase64) {
            clearImageBtn.click();
        }
        ingredientInput.value = med;
        runAnalysis(med, false);
    });
});

// iCal download generator (.ics)
reminderBtn.addEventListener('click', () => {
    if (!currentIngredient) return;
    
    const now = new Date();
    const formatDate = (d) => {
        return d.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
    };
    
    const start = new Date(now.getTime() + 60 * 60 * 1000); // 1 hour from now
    const end = new Date(start.getTime() + 30 * 60 * 1000); // 30 minutes duration
    
    const startStr = formatDate(start);
    const endStr = formatDate(end);
    const stampStr = formatDate(now);
    
    const summary = currentLang === 'zh' 
        ? `服藥提醒：${currentIngredient} - MediSafe` 
        : `Take ${currentIngredient} - MediSafe Reminder`;
        
    const description = currentLang === 'zh'
        ? `提醒您按時服用藥物 (${currentIngredient})。請參考 MediSafe 中安全說明與食物交互警告。`
        : `Reminder to take your medication (${currentIngredient}) as scheduled. Please check safety instructions and food warnings in MediSafe.`;
    
    const icsContent = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//MediSafe//Dose Reminder//EN",
        "BEGIN:VEVENT",
        `UID:${stampStr}-medisafe`,
        `DTSTAMP:${stampStr}`,
        `DTSTART:${startStr}`,
        `DTEND:${endStr}`,
        `SUMMARY:${summary}`,
        `DESCRIPTION:${description}`,
        "RRULE:FREQ=DAILY;INTERVAL=1;COUNT=7", // repeat daily for 7 days
        "BEGIN:VALARM",
        "TRIGGER:-PT15M", // alarm 15 minutes before
        "ACTION:DISPLAY",
        "DESCRIPTION:Reminder: Time to take your medication",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR"
    ].join("\r\n");
    
    const blob = new Blob([icsContent], { type: 'text/calendar;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${currentIngredient.replace(/\s+/g, '_')}_reminder.ics`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
});

// PDF Print trigger
pdfBtn.addEventListener('click', () => {
    window.print();
});

// Follow-up Chat logic
async function sendChatMessage() {
    const text = chatInput.value.trim();
    if (!text || !currentIngredient || !currentReportMarkdown) return;
    
    // Add user message bubble
    const userBubble = document.createElement('div');
    userBubble.className = 'chat-message user-message';
    userBubble.innerText = text;
    chatHistory.appendChild(userBubble);
    chatInput.value = "";
    
    // Scroll chat to bottom
    chatHistory.scrollTop = chatHistory.scrollHeight;
    
    // Add bot typing loading indicator
    const typingBubble = document.createElement('div');
    typingBubble.className = 'chat-message bot-message typing-indicator';
    typingBubble.innerText = currentLang === 'zh' ? "藥劑師正在分析中..." : "Pharmacist is thinking...";
    chatHistory.appendChild(typingBubble);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    
    try {
        const payload = {
            ingredient: currentIngredient,
            report: currentReportMarkdown,
            message: text,
            lang: currentLang
        };
        
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        const data = await response.json();
        
        // Remove loading indicator bubble
        chatHistory.removeChild(typingBubble);
        
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to get chat response');
        }
        
        const botBubble = document.createElement('div');
        botBubble.className = 'chat-message bot-message';
        botBubble.innerText = data.response;
        chatHistory.appendChild(botBubble);
        
    } catch (err) {
        if (chatHistory.contains(typingBubble)) {
            chatHistory.removeChild(typingBubble);
        }
        const errorBubble = document.createElement('div');
        errorBubble.className = 'chat-message bot-message alert-warning';
        errorBubble.innerText = currentLang === 'zh' 
            ? `錯誤：無法連接至 AI 藥劑師 (${err.message})` 
            : `Error: Could not reach AI Pharmacist (${err.message})`;
        chatHistory.appendChild(errorBubble);
    }
    
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

sendChatBtn.addEventListener('click', sendChatMessage);
chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendChatMessage();
    }
});

// Setup default placeholders on page load
applyLocalization('en');
