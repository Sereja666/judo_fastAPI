// ========== API функции ==========
const visitsTodayApi = {
    async loadPlaces() {
        try {
            const response = await fetch('/visits-today/get-places');
            if (!response.ok) throw new Error('Ошибка сети');
            return await response.json();
        } catch (error) {
            console.error('Ошибка загрузки мест:', error);
            throw error;
        }
    },
    // ... остальные функции из visits_today_api.js
};

// ========== UI функции ==========
const visitsTodayUI = {
    showStep(step) {
        document.querySelectorAll('.visits-step').forEach(el => {
            el.classList.add('d-none');
        });
        const stepElement = document.getElementById(`step${step}`);
        if (stepElement) {
            stepElement.classList.remove('d-none');
        }
    },
    // ... остальные функции из visits_today_ui.js
};

// ========== Основная логика ==========
const visitsToday = {
    state: {
        currentStep: 1,
        selectedPlace: null,
        selectedTraining: null,
        scheduleId: null,
        selectedStudents: new Set(),
        extraStudents: new Map(),
        searchTimeout: null
    },

    init() {
        console.log('Инициализация системы посещений...');
        this.loadPlaces();
        this.setupEventListeners();
    },
    // ... остальные функции из visits_today_main.js
};

// Экспортируем для глобального доступа
window.visitsTodayApi = visitsTodayApi;
window.visitsTodayUI = visitsTodayUI;
window.visitsToday = visitsToday;