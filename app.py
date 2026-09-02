<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MySales Trend - Smart Product Research Engine</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body class="bg-gray-100 font-sans flex h-screen overflow-hidden">

    <!-- Сайдбар Smart Query Engine -->
    <aside class="w-80 bg-gray-50 border-r border-gray-200 p-4 flex flex-col justify-between overflow-y-auto">
        <div>
            <div class="flex items-center gap-2 mb-4">
                <i class="fa-solid fa-eye text-gray-700"></i>
                <h2 class="font-bold text-gray-800 text-lg">Smart Query Engine</h2>
            </div>

            <div class="text-sm text-gray-500 mb-4">
                <i class="fa-regular fa-lightbulb"></i> В пулі гіпотез: <span id="poolCount" class="font-bold text-gray-800">0</span> фраз 
                (з них AI: <span id="aiPoolCount" class="font-bold text-gray-800">0</span>)
            </div>

            <div class="grid grid-cols-2 gap-2 mb-6">
                <button id="btnGenerate" class="px-3 py-2 bg-white border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 flex items-center justify-center gap-1 shadow-sm">
                    <i class="fa-solid fa-dice text-gray-500"></i> Згенерув...
                </button>
                <button id="btnCombinator" class="px-3 py-2 bg-white border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 flex items-center justify-center gap-1 shadow-sm">
                    <i class="fa-solid fa-puzzle-piece text-green-600"></i> Комбінатор
                </button>
            </div>

            <!-- Блок налаштування Gemini AI -->
            <div class="border border-gray-200 rounded-lg bg-white overflow-hidden shadow-sm mb-4">
                <div class="w-full px-4 py-3 bg-gray-50 flex justify-between items-center text-sm font-semibold text-gray-700 border-b border-gray-200">
                    <span class="flex items-center gap-2">
                        <i class="fa-solid fa-wand-magic-sparkles text-amber-500"></i> Налаштування Gemini AI
                    </span>
                </div>
                
                <div class="p-4 space-y-4">
                    <div>
                        <div class="flex justify-between items-center mb-1">
                            <label class="text-xs font-semibold text-gray-600">Gemini API Key:</label>
                        </div>
                        <div class="relative">
                            <input type="password" id="apiKeyInput" placeholder="Встав свій API ключ сюди..." 
                                   class="w-full text-xs p-2 pr-8 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:outline-none">
                            <button id="toggleKeyVisibility" class="absolute right-2 top-2 text-gray-400 hover:text-gray-600">
                                <i class="fa-regular fa-eye text-xs"></i>
                            </button>
                        </div>
                    </div>

                    <button id="btnFillAI" class="w-full py-2 bg-white border border-gray-300 rounded-lg text-xs font-medium text-gray-700 hover:bg-gray-50 flex items-center justify-center gap-2 shadow-sm transition">
                        <i class="fa-solid fa-rocket text-blue-500"></i> Наповнити пул через AI (+30 фраз)
                    </button>

                    <!-- Контейнер для помилок -->
                    <div id="errorContainer" class="hidden p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-600 font-mono break-words leading-relaxed"></div>
                </div>
            </div>

            <!-- Пул гіпотез -->
            <div class="mt-4">
                <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Активний пул</h3>
                <ul id="queryList" class="space-y-1 text-xs text-gray-600 max-h-60 overflow-y-auto">
                    <li class="italic text-gray-400">Пул порожній</li>
                </ul>
            </div>
        </div>
    </aside>

    <!-- Основний контент -->
    <main class="flex-1 p-8 overflow-y-auto">
        <div class="flex items-center justify-between mb-6">
            <div class="flex items-center gap-3">
                <div class="p-2 bg-blue-100 rounded-lg text-blue-600">
                    <i class="fa-solid fa-chart-column text-2xl"></i>
                </div>
                <h1 class="text-3xl font-extrabold text-gray-900 tracking-tight">
                    MySales Trend: <span class="font-normal text-gray-700">Smart Product Research Engine</span>
                </h1>
            </div>
        </div>

        <button id="btnStartScan" class="px-6 py-3 bg-red-500 hover:bg-red-600 text-white font-semibold rounded-lg shadow flex items-center gap-2 transition mb-8">
            <i class="fa-solid fa-rocket"></i> Запустити сканування
        </button>

        <hr class="border-gray-200 mb-6">

        <div class="flex gap-8 border-b border-gray-200 mb-6 text-sm font-medium">
            <button class="pb-3 text-red-500 border-b-2 border-red-500 flex items-center gap-2">
                <i class="fa-regular fa-clipboard"></i> Знайдено товарів (<span id="foundCount">0</span>)
            </button>
            <button class="pb-3 text-gray-500 hover:text-gray-700 flex items-center gap-2">
                <i class="fa-regular fa-star"></i> Обране в БД (0)
            </button>
            <button class="pb-3 text-gray-500 hover:text-gray-700 flex items-center gap-2">
                <i class="fa-solid fa-chart-line"></i> Аналітика ніші
            </button>
            <button class="pb-3 text-gray-500 hover:text-gray-700 flex items-center gap-2">
                <i class="fa-solid fa-magnifying-glass"></i> SEO & Ключові слова
            </button>
        </div>

        <div class="p-4 bg-blue-50 border border-blue-100 rounded-lg text-sm text-blue-800 flex items-center gap-2">
            <i class="fa-regular fa-lightbulb text-amber-500 text-lg"></i>
            <span>Натисніть '<strong>🚀 Запустити сканування</strong>' або кнопку '<strong>🎲 Згенерив...</strong>' в меню ліворуч.</span>
        </div>
    </main>

    <script>
        const state = {
            pool: [],
            aiCount: 0
        };

        const apiKeyInput = document.getElementById('apiKeyInput');
        const btnFillAI = document.getElementById('btnFillAI');
        const errorContainer = document.getElementById('errorContainer');
        const poolCount = document.getElementById('poolCount');
        const aiPoolCount = document.getElementById('aiPoolCount');
        const queryList = document.getElementById('queryList');
        const toggleKeyVisibility = document.getElementById('toggleKeyVisibility');

        // Перемикач видимості ключа
        toggleKeyVisibility.addEventListener('click', () => {
            const isPassword = apiKeyInput.type === 'password';
            apiKeyInput.type = isPassword ? 'text' : 'password';
            toggleKeyVisibility.querySelector('i').className = isPassword ? 'fa-regular fa-eye-slash text-xs' : 'fa-regular fa-eye text-xs';
        });

        // Запит до Gemini API
        btnFillAI.addEventListener('click', async () => {
            const apiKey = apiKeyInput.value.trim();
            errorContainer.classList.add('hidden');
            errorContainer.innerText = '';

            if (!apiKey) {
                showError("Помилка: Вкажіть Gemini API Key!");
                return;
            }

            btnFillAI.disabled = true;
            btnFillAI.innerHTML = `<i class="fa-solid fa-spinner fa-spin text-blue-500"></i> Генерація...`;

            // ВИПРАВЛЕННЯ ОШИБКИ 404: заменено gemini-1.5-flash-latest на gemini-1.5-flash
            const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`;

            const promptText = `Ты — эксперт по e-commerce и товарной аналитике. 
Сгенерируй 30 трендовых поисковых запросов и гипотез для поиска вирусных товаров (dropshipping/e-commerce). 
Выведи строго список из 30 фраз на украинском языке, по одной на строке, без нумерации, без маркдауна и пояснений.`;

            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        contents: [{
                            parts: [{ text: promptText }]
                        }]
                    })
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(`Помилка Gemini API: ${response.status} - ${JSON.stringify(data, null, 2)}`);
                }

                const rawText = data.candidates?.[0]?.content?.parts?.[0]?.text || '';
                const newPhrases = rawText
                    .split('\n')
                    .map(line => line.replace(/^[\d\.\*\-\s]+/, '').trim())
                    .filter(line => line.length > 0);

                state.pool.push(...newPhrases);
                state.aiCount += newPhrases.length;

                renderPool();

            } catch (err) {
                showError(err.message);
            } finally {
                btnFillAI.disabled = false;
                btnFillAI.innerHTML = `<i class="fa-solid fa-rocket text-blue-500"></i> Наповнити пул через AI (+30 фраз)`;
            }
        });

        function showError(msg) {
            errorContainer.innerText = msg;
            errorContainer.classList.remove('hidden');
        }

        function renderPool() {
            poolCount.innerText = state.pool.length;
            aiPoolCount.innerText = state.aiCount;

            if (state.pool.length === 0) {
                queryList.innerHTML = `<li class="italic text-gray-400">Пул порожній</li>`;
                return;
            }

            queryList.innerHTML = state.pool.map((q, idx) => `
                <li class="py-1 px-2 bg-white border border-gray-200 rounded flex justify-between items-center text-xs">
                    <span class="truncate">${idx + 1}. ${q}</span>
                    <i class="fa-solid fa-xmark text-gray-300 hover:text-red-500 cursor-pointer" onclick="removePhrase(${idx})"></i>
                </li>
            `).join('');
        }

        window.removePhrase = function(index) {
            state.pool.splice(index, 1);
            renderPool();
        };
    </script>
</body>
</html>
