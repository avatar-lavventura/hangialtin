const API_BASE_URL = 'http://localhost:8000/api';

// DOM Elements
const loading = document.getElementById('loading');
const error = document.getElementById('error');
const results = document.getElementById('results');
const recommendation = document.getElementById('recommendation');
const etfList = document.getElementById('etfList');

// Load comparison on page load
window.addEventListener('load', () => {
    compareETFs();
});

async function compareETFs() {
    showLoading();
    hideError();
    hideResults();

    try {
        // Fetch all ETFs comparison
        const response = await fetch(`${API_BASE_URL}/gold-etf/compare`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        displayResults(data);
    } catch (err) {
        showError(`Hata: ${err.message}. Backend'in çalıştığından emin olun (http://localhost:8000)`);
    } finally {
        hideLoading();
    }
}

function displayResults(data) {
    console.log('displayResults called with data:', data);
    
    // Display recommendation
    if (recommendation) {
        recommendation.innerHTML = `
            <h2>💡 Gram Başına Fiyatına Göre Öneri</h2>
            <p>${data.recommendation}</p>
            <p style="margin-top: 10px; font-size: 0.9rem; color: #666; font-style: italic;">
                Not: Karşılaştırma gram başına fiyatına (TL/gram) göre yapılmaktadır. En düşük gram başına fiyatlı ETF en ucuz seçenektir.
            </p>
        `;
    }

    // Display ETF list
    if (etfList) {
        etfList.innerHTML = '';
    }
    
    // Calculate per-gram prices for all ETFs to determine cheapest
    const etfsWithPerGram = data.all_etfs
        .filter(etf => etf.gold_backing_grams)
        .map(etf => ({
            etf,
            perGramPrice: etf.current_price / etf.gold_backing_grams
        }))
        .sort((a, b) => a.perGramPrice - b.perGramPrice);
    
    const cheapestPerGramPrice = etfsWithPerGram.length > 0 ? etfsWithPerGram[0].perGramPrice : null;
    const cheapestEtfSymbol = etfsWithPerGram.length > 0 ? etfsWithPerGram[0].etf.symbol : null;
    
    // Calculate base value between ZGOLD and GLDTR
    // Formula: ZGOLD fiyatı ≈ GLDTR / baz_değer
    // baz_değer = GLDTR fiyatı / ZGOLD fiyatı
    const zgoldEtf = data.all_etfs.find(etf => etf.symbol === 'ZGOLD');
    const gldtrEtf = data.all_etfs.find(etf => etf.symbol === 'GLDTR');
    let baseValue = null;
    if (zgoldEtf && gldtrEtf && zgoldEtf.current_price > 0 && gldtrEtf.current_price > 0) {
        baseValue = gldtrEtf.current_price / zgoldEtf.current_price;
    }
    
    // Display base value comparison for all ETFs
    // Baz değer = Altın karşılığı (gram) = ETF Fiyatı / Gram Altın Fiyatı
    const baseValueComparison = document.getElementById('baseValueComparison');
    
    // Debug: Log all ETFs data
    console.log('All ETFs Data:', data.all_etfs.map(etf => ({
        symbol: etf.symbol,
        current_price: etf.current_price,
        gold_backing_grams: etf.gold_backing_grams
    })));
    
    // Get spot gram gold price for calculation
    const spotGramGoldPrice = data.spot_gram_gold_price || null;
    
    // Calculate base values (gold backing) for all ETFs
    // Formula: 1 gramın maliyeti = ETF pay fiyatı / 1 payın temsil ettiği gram
    // Yani: perGramPrice = current_price / gold_backing_grams
    const etfsWithBaseValue = data.all_etfs
        .filter(etf => etf.current_price > 0 && etf.gold_backing_grams && etf.gold_backing_grams > 0) // Must have both price and gold_backing_grams
        .map(etf => {
            // Use gold_backing_grams from backend (already calculated correctly)
            const goldBacking = etf.gold_backing_grams;
            
            // Calculate per gram price: ETF pay fiyatı / 1 payın temsil ettiği gram
            const perGramPrice = etf.current_price / goldBacking;
            
            return {
                etf,
                baseValue: goldBacking, // Altın karşılığı = baz değer (g₁, g₂, g₃)
                perGramPrice: perGramPrice, // 1 gramın maliyeti = F / g
                formula: etf.symbol === 'ZGOLD' 
                    ? 'ZGOLD Fiyatı = Altın karşılığı × Gram altın fiyatı'
                    : etf.symbol === 'GLDTR'
                    ? 'GLDTR Fiyatı = Altın karşılığı × Gram altın fiyatı'
                    : 'ETF Fiyatı = Altın karşılığı × Gram altın fiyatı'
            };
        })
        .sort((a, b) => a.perGramPrice - b.perGramPrice); // Sort by per-gram price (best value first)
    
    // Always show comparison table
    console.log('baseValueComparison element:', baseValueComparison);
    console.log('etfsWithBaseValue length:', etfsWithBaseValue.length);
    console.log('results element:', results);
    
    // Make sure results div is visible first
    if (results) {
        results.classList.remove('hidden');
        results.style.display = 'block';
        console.log('Results div made visible');
    }
    
    if (baseValueComparison) {
        if (etfsWithBaseValue.length === 0) {
            // No ETFs with gold backing data
            baseValueComparison.innerHTML = `
                <div style="padding: 20px; text-align: center; color: #666;">
                    <p>ETF verileri yükleniyor veya altın karşılığı bilgisi bulunamadı.</p>
                    <p style="font-size: 0.9rem; margin-top: 10px;">Lütfen birkaç saniye bekleyip tekrar deneyin.</p>
                </div>
            `;
            baseValueComparison.style.display = 'block';
        } else {
            const bestValueEtf = etfsWithBaseValue[0];
            
            // Get spot gram gold price from API response
            const spotGramGoldPrice = data.spot_gram_gold_price || null;
            
            // Debug: Log values
            console.log('ETF Comparison Debug:', {
                etfsCount: etfsWithBaseValue.length,
                bestValueEtf: bestValueEtf.etf.symbol,
                bestPerGramPrice: bestValueEtf.perGramPrice,
                spotGramGoldPrice: spotGramGoldPrice
            });
            
            // Check if any ETF has NAV data
            const hasNavData = etfsWithBaseValue.some(item => item.etf.nav_price && item.etf.nav_price > 0);
            
            // Debug: Log NAV data
            console.log('NAV Debug:', {
                hasNavData: hasNavData,
                etfs: etfsWithBaseValue.map(item => ({
                    symbol: item.etf.symbol,
                    nav_price: item.etf.nav_price,
                    current_price: item.etf.current_price
                }))
            });
            
            // Build comparison table
            let tableHTML = `
            <h2>📊 ETF Karşılaştırma Tablosu</h2>
            ${spotGramGoldPrice ? `
            <div style="margin-top: 10px; margin-bottom: 15px; padding: 12px 15px; background: rgba(255, 193, 7, 0.15); border-radius: 8px; border-left: 4px solid #FFC107;">
                <div style="font-size: 0.95rem; color: #333; font-weight: 600;">
                    💰 Spot Gram Altın Fiyatı: <strong style="color: #FF9800;">${formatPrice(spotGramGoldPrice)} TL/gram</strong>
                </div>
                <div style="font-size: 0.85rem; color: #666; margin-top: 5px;">
                    Bu fiyat, ETF'lerin altın karşılığını hesaplamak için kullanılmaktadır.
                </div>
            </div>
            ` : ''}
            <div style="overflow-x: auto; margin-top: 15px;">
                <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <thead>
                        <tr style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">
                            <th style="padding: 12px 15px; text-align: left; font-weight: 600;">Fon</th>
                            <th style="padding: 12px 15px; text-align: right; font-weight: 600;">1 Payda Kaç Gram<br><span style="font-size: 0.85rem; font-weight: 400;">(g₁, g₂, g₃)</span></th>
                            <th style="padding: 12px 15px; text-align: right; font-weight: 600;">Borsada Kaç TL Ödüyorsun<br><span style="font-size: 0.85rem; font-weight: 400;">(F₁, F₂, F₃)</span></th>
                            ${hasNavData ? `
                            <th style="padding: 12px 15px; text-align: right; font-weight: 600;">NAV (Birim Fiyatı)<br><span style="font-size: 0.85rem; font-weight: 400;">(~değer)</span></th>
                            ` : ''}
                            <th style="padding: 12px 15px; text-align: right; font-weight: 600;">Stopaj<br><span style="font-size: 0.85rem; font-weight: 400;">(%)</span></th>
                            <th style="padding: 12px 15px; text-align: right; font-weight: 600;">Yönetim Ücreti<br><span style="font-size: 0.85rem; font-weight: 400;">(%)</span></th>
                            <th style="padding: 12px 15px; text-align: right; font-weight: 600;">1 Gramı Kaça Alıyorsun<br><span style="font-size: 0.85rem; font-weight: 400;">(F₁/g₁, F₂/g₂, F₃/g₃)</span></th>
                        </tr>
                    </thead>
                    <tbody>
        `;
            
            etfsWithBaseValue.forEach((item, index) => {
            const isBest = index === 0;
            const etf = item.etf;
            
            // Recalculate per gram price to ensure accuracy: ETF pay fiyatı / 1 payın temsil ettiği gram
            const perGramPrice = etf.current_price / etf.gold_backing_grams;
            
            // Format stopaj and expense ratio
            const stopajDisplay = etf.stopaj_rate !== null && etf.stopaj_rate !== undefined 
                ? `${etf.stopaj_rate.toFixed(2)}%` 
                : '<span style="color: #999;">-</span>';
            const expenseDisplay = etf.expense_ratio !== null && etf.expense_ratio !== undefined 
                ? `${etf.expense_ratio.toFixed(2)}%` 
                : '<span style="color: #999;">-</span>';
            
            // Debug log
            console.log(`${etf.symbol}: price=${etf.current_price}, gold_backing=${etf.gold_backing_grams}, per_gram=${perGramPrice.toFixed(2)}`);
            
            const cheapestPerGramPrice = bestValueEtf.perGramPrice;
            const priceDiffPercent = isBest ? 0 : ((perGramPrice - cheapestPerGramPrice) / cheapestPerGramPrice * 100);
            const priceDiffAbsolute = isBest ? 0 : (perGramPrice - cheapestPerGramPrice);
            const rowStyle = isBest 
                ? 'background: rgba(76, 175, 80, 0.15); border-left: 4px solid #4CAF50; font-weight: 600;' 
                : index % 2 === 0 
                ? 'background: rgba(0,0,0,0.02);' 
                : '';
            
            tableHTML += `
                        <tr style="${rowStyle}">
                            <td style="padding: 12px 15px;">
                                ${etf.symbol}
                                ${isBest ? '<span style="background: #4CAF50; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; margin-left: 8px;">EN UYGUN</span>' : ''}
                            </td>
                            <td style="padding: 12px 15px; text-align: right; font-family: "Courier New", monospace;">
                                <div style="font-weight: 600; color: #2196F3;">
                                    ${item.baseValue.toFixed(6)} gram
                                </div>
                                ${etf.nav_price && etf.nav_price > 0 ? `
                                <div style="font-size: 0.75rem; color: #4CAF50; margin-top: 3px; font-style: italic;">
                                    ✨ NAV'dan güncellendi
                                </div>
                                ` : `
                                <div style="font-size: 0.75rem; color: #999; margin-top: 3px; font-style: italic;">
                                    (sabit değer)
                                </div>
                                `}
                            </td>
                            <td style="padding: 12px 15px; text-align: right; font-family: "Courier New", monospace;">
                                ${formatPrice(etf.current_price)} TL
                            </td>
                            ${hasNavData ? `
                            <td style="padding: 12px 15px; text-align: right; font-family: "Courier New", monospace;">
                                ${etf.nav_price ? `
                                <div style="color: #2196F3; font-weight: 600;">
                                    ~${formatPrice(etf.nav_price)} TL
                                </div>
                                ${etf.nav_price && etf.current_price ? (() => {
                                    const navDiff = etf.current_price - etf.nav_price;
                                    const navDiffPercent = (navDiff / etf.nav_price) * 100;
                                    const isPremium = navDiff > 0;
                                    return `
                                    <div style="font-size: 0.75rem; color: ${isPremium ? '#f44336' : '#4CAF50'}; margin-top: 3px;">
                                        ${isPremium ? '+' : ''}${formatPrice(navDiff)} TL (${isPremium ? '+' : ''}${navDiffPercent.toFixed(2)}%)
                                        <span style="font-size: 0.7rem; color: #666;">${isPremium ? 'primli' : 'iskontolu'}</span>
                                    </div>
                                    `;
                                })() : ''}
                                ` : '<span style="color: #999; font-size: 0.85rem;">N/A</span>'}
                            </td>
                            ` : ''}
                            <td style="padding: 12px 15px; text-align: right; font-family: "Courier New", monospace;">
                                ${stopajDisplay}
                            </td>
                            <td style="padding: 12px 15px; text-align: right; font-family: "Courier New", monospace;">
                                ${expenseDisplay}
                            </td>
                            <td style="padding: 12px 15px; text-align: right;">
                                <div style="color: #4CAF50; font-weight: ${isBest ? '700' : '600'}; font-family: "Courier New", monospace;">
                                    ${formatPrice(perGramPrice)} TL/gram
                                </div>
                                ${!isBest ? `
                                <div style="font-size: 0.75rem; color: #f44336; margin-top: 4px; font-weight: 600;">
                                    +${formatPrice(priceDiffAbsolute)} TL (+${priceDiffPercent.toFixed(2)}%)
                                </div>
                                ` : ''}
                            </td>
                        </tr>
            `;
            });
            
            tableHTML += `
                    </tbody>
                </table>
            </div>
        `;
            
            // Add best value summary
            let comparisonHTML = `
            ${tableHTML}
            <div style="margin-top: 20px; padding: 15px; background: rgba(76, 175, 80, 0.15); border-radius: 8px; border-left: 4px solid #4CAF50;">
                <div style="font-size: 0.95rem; color: #333; margin-bottom: 10px; font-weight: 700;">
                    ✅ En Uygun Seçenek: <strong style="color: #4CAF50;">${bestValueEtf.etf.symbol}</strong>
                </div>
                <div style="font-size: 0.9rem; color: #666; margin-bottom: 5px;">
                    <strong>1 Payda Altın Karşılığı:</strong> ${bestValueEtf.baseValue.toFixed(6)} gram
                </div>
                <div style="font-size: 0.9rem; color: #666; margin-bottom: 5px;">
                    <strong>Borsada Ödenen:</strong> ${formatPrice(bestValueEtf.etf.current_price)} TL
                </div>
                <div style="font-size: 0.9rem; color: #666; margin-bottom: 10px;">
                    <strong>1 Gramı Kaça Alıyorsun:</strong> <strong style="color: #4CAF50; font-size: 1.1rem;">${formatPrice(bestValueEtf.perGramPrice)} TL/gram</strong>
                </div>
                <div style="margin-top: 15px; padding-top: 15px; border-top: 2px solid rgba(76, 175, 80, 0.3);">
                    <div style="font-size: 0.9rem; color: #333; margin-bottom: 10px; font-weight: 600;">📊 Diğer ETF'lerle TL/gram Karşılaştırması:</div>
                    ${etfsWithBaseValue.slice(1).map(item => {
                        const diffPercent = ((item.perGramPrice - bestValueEtf.perGramPrice) / bestValueEtf.perGramPrice * 100);
                        const diffAbsolute = item.perGramPrice - bestValueEtf.perGramPrice;
                        return `
                        <div style="font-size: 0.85rem; color: #666; margin-bottom: 8px; padding: 8px; background: rgba(255, 255, 255, 0.5); border-radius: 4px;">
                            <strong>${item.etf.symbol}:</strong> ${formatPrice(item.perGramPrice)} TL/gram 
                            <span style="color: #f44336; font-weight: 600;">(+${formatPrice(diffAbsolute)} TL, +${diffPercent.toFixed(2)}% daha pahalı)</span>
                        </div>
                        `;
                    }).join('')}
                </div>
                <div style="font-size: 0.85rem; color: #888; font-style: italic; margin-top: 12px;">
                    Formül: ${bestValueEtf.formula}
                </div>
            </div>
            <div style="margin-top: 15px; padding: 15px; background: rgba(102, 126, 234, 0.1); border-radius: 8px; border-left: 4px solid #667eea;">
                <div style="font-size: 0.9rem; color: #666; margin-bottom: 8px; font-weight: 600;">📐 Hesaplama Formülü</div>
                <div style="font-size: 0.85rem; color: #333; line-height: 1.8; font-family: 'Courier New', monospace;">
                    ${spotGramGoldPrice ? `
                    <div style="margin-bottom: 10px; padding: 8px; background: rgba(255, 255, 255, 0.5); border-radius: 4px;">
                        <strong>Adım 1:</strong> Altın Karşılığı (g) = ETF Fiyatı (F) ÷ Spot Gram Altın Fiyatı (${formatPrice(spotGramGoldPrice)} TL/gram)
                    </div>
                    ` : ''}
                    <div style="margin-bottom: 10px; padding: 8px; background: rgba(255, 255, 255, 0.5); border-radius: 4px;">
                        <strong>Adım 2:</strong> 1 Gram Fiyatı (TL/gram) = ETF Fiyatı (F) ÷ Altın Karşılığı (g)
                    </div>
                    ${spotGramGoldPrice ? `
                    <div style="margin-top: 10px; margin-bottom: 5px; font-weight: 600;">Hesaplama Örnekleri:</div>
                    ${etfsWithBaseValue.find(e => e.etf.symbol === 'ZGOLD') ? (() => {
                        const zgold = etfsWithBaseValue.find(e => e.etf.symbol === 'ZGOLD');
                        return `<div style="margin-bottom: 5px;">ZGOLD: g₁ = ${formatPrice(zgold.etf.current_price)} ÷ ${formatPrice(spotGramGoldPrice)} = ${zgold.baseValue.toFixed(6)} gram → F₁/g₁ = ${formatPrice(zgold.etf.current_price)} ÷ ${zgold.baseValue.toFixed(6)} = ${formatPrice(zgold.perGramPrice)} TL/gram</div>`;
                    })() : ''}
                    ${etfsWithBaseValue.find(e => e.etf.symbol === 'GLDTR') ? (() => {
                        const gldtr = etfsWithBaseValue.find(e => e.etf.symbol === 'GLDTR');
                        return `<div style="margin-bottom: 5px;">GLDTR: g₂ = ${formatPrice(gldtr.etf.current_price)} ÷ ${formatPrice(spotGramGoldPrice)} = ${gldtr.baseValue.toFixed(6)} gram → F₂/g₂ = ${formatPrice(gldtr.etf.current_price)} ÷ ${gldtr.baseValue.toFixed(6)} = ${formatPrice(gldtr.perGramPrice)} TL/gram</div>`;
                    })() : ''}
                    ${etfsWithBaseValue.find(e => e.etf.symbol === 'ISGLK') ? (() => {
                        const isglk = etfsWithBaseValue.find(e => e.etf.symbol === 'ISGLK');
                        return `<div style="margin-bottom: 5px;">ISGLK: g₃ = ${formatPrice(isglk.etf.current_price)} ÷ ${formatPrice(spotGramGoldPrice)} = ${isglk.baseValue.toFixed(6)} gram → F₃/g₃ = ${formatPrice(isglk.etf.current_price)} ÷ ${isglk.baseValue.toFixed(6)} = ${formatPrice(isglk.perGramPrice)} TL/gram</div>`;
                    })() : ''}
                    ` : `
                    <div style="margin-bottom: 5px;">ZGOLD: F₁ ÷ g₁ = ${formatPrice(etfsWithBaseValue.find(e => e.etf.symbol === 'ZGOLD')?.etf.current_price || 0)} ÷ ${etfsWithBaseValue.find(e => e.etf.symbol === 'ZGOLD')?.baseValue.toFixed(6) || '0'} = ${formatPrice(etfsWithBaseValue.find(e => e.etf.symbol === 'ZGOLD')?.perGramPrice || 0)} TL/gram</div>
                    ${etfsWithBaseValue.find(e => e.etf.symbol === 'GLDTR') ? `<div style="margin-bottom: 5px;">GLDTR: F₂ ÷ g₂ = ${formatPrice(etfsWithBaseValue.find(e => e.etf.symbol === 'GLDTR')?.etf.current_price || 0)} ÷ ${etfsWithBaseValue.find(e => e.etf.symbol === 'GLDTR')?.baseValue.toFixed(6) || '0'} = ${formatPrice(etfsWithBaseValue.find(e => e.etf.symbol === 'GLDTR')?.perGramPrice || 0)} TL/gram</div>` : ''}
                    ${etfsWithBaseValue.find(e => e.etf.symbol === 'ISGLK') ? `<div style="margin-bottom: 5px;">ISGLK: F₃ ÷ g₃ = ${formatPrice(etfsWithBaseValue.find(e => e.etf.symbol === 'ISGLK')?.etf.current_price || 0)} ÷ ${etfsWithBaseValue.find(e => e.etf.symbol === 'ISGLK')?.baseValue.toFixed(6) || '0'} = ${formatPrice(etfsWithBaseValue.find(e => e.etf.symbol === 'ISGLK')?.perGramPrice || 0)} TL/gram</div>` : ''}
                    `}
                </div>
                ${spotGramGoldPrice ? `
                <div style="margin-top: 12px; padding: 10px; background: rgba(255, 193, 7, 0.1); border-radius: 4px; font-size: 0.8rem; color: #666; line-height: 1.6;">
                    <strong>💡 Not:</strong> Bu hesaplama spot gram altın fiyatına (${formatPrice(spotGramGoldPrice)} TL/gram) göre yapılmıştır. 
                    Gerçek NAV (Net Aktif Değer) ve fonun portföyündeki altın miktarına göre daha kesin sonuçlar için fonların resmi raporlarına bakılmalıdır.
                </div>
                ` : ''}
            </div>
        `;
        
            baseValueComparison.innerHTML = comparisonHTML;
            baseValueComparison.style.display = 'block'; // Ensure it's visible
            baseValueComparison.style.visibility = 'visible'; // Double check
            console.log('Table rendered successfully, length:', comparisonHTML.length);
        }
    } else {
        console.error('baseValueComparison element not found in DOM!');
    }
    
    // Ensure results div is visible
    if (results) {
        results.classList.remove('hidden');
        results.style.display = 'block';
        console.log('Results div made visible');
    }
    
    // Always show results div - do this early to ensure visibility
    if (results) {
        results.classList.remove('hidden');
        results.style.display = 'block';
    }
    
    data.all_etfs.forEach(etf => {
        // Calculate per-gram price if gold backing is available
        const perGramPrice = etf.gold_backing_grams ? (etf.current_price / etf.gold_backing_grams) : null;
        
        // Determine if this ETF is cheapest based on per-gram price
        // Compare with backend's cheapest or calculate locally
        const isCheapest = etf.gold_backing_grams && cheapestPerGramPrice 
            ? Math.abs(perGramPrice - cheapestPerGramPrice) < 0.0001  // Compare with small tolerance for floating point
            : false;
        
        const priceDiff = data.price_difference[etf.symbol];
        
        const etfCard = document.createElement('div');
        etfCard.className = `etf-card ${isCheapest ? 'cheapest' : ''}`;
        
        const changeClass = etf.change_percent >= 0 ? 'positive' : 'negative';
        const changeSymbol = etf.change_percent >= 0 ? '+' : '';
        
        const priceDiffPerGram = priceDiff && priceDiff.per_gram_price ? priceDiff.per_gram_price : null;
        
        etfCard.innerHTML = `
            <div class="etf-info">
                <div class="etf-header">
                    <span class="etf-name">${etf.name}</span>
                    ${isCheapest ? '<span class="badge">EN UCUZ</span>' : ''}
                </div>
                ${perGramPrice ? `
                <div class="etf-price" style="font-size: 1.8rem; font-weight: 700; color: #4CAF50; margin: 12px 0;">
                    ${formatPrice(perGramPrice)} TL/gram
                </div>
                ` : `
                <div class="etf-price">${formatPrice(etf.current_price)} TL</div>
                `}
                <div class="etf-details">
                    <div class="etf-detail">
                        <span class="etf-detail-label">Değişim</span>
                        <span class="etf-change ${changeClass}">
                            ${changeSymbol}${etf.change_percent?.toFixed(2) || '0.00'}%
                        </span>
                    </div>
                    ${etf.volume ? `
                    <div class="etf-detail">
                        <span class="etf-detail-label">Hacim</span>
                        <span class="etf-change">${formatNumber(etf.volume)}</span>
                    </div>
                    ` : ''}
                    ${etf.last_updated ? `
                    <div class="etf-detail">
                        <span class="etf-detail-label">Güncelleme</span>
                        <span class="etf-change">${formatDate(etf.last_updated)}</span>
                    </div>
                    ` : ''}
                    ${etf.gold_backing_grams ? `
                    <div class="etf-detail">
                        <span class="etf-detail-label">Altın Karşılığı</span>
                        <span class="etf-change">${etf.gold_backing_grams} gram</span>
                    </div>
                    ` : ''}
                </div>
                ${priceDiff && priceDiffPerGram && cheapestPerGramPrice ? `
                <div class="price-diff">
                    <div class="price-diff-label">Gram başına fiyat farkı (en ucuzdan):</div>
                    <div class="price-diff-value">
                        +${formatPrice(priceDiffPerGram - cheapestPerGramPrice)} TL/gram (%${priceDiff.percent.toFixed(2)})
                    </div>
                </div>
                ` : ''}
                ${etf.symbol === 'ZGOLD' && etf.gold_backing_grams ? `
                <div class="formula-info" style="margin-top: 15px; padding: 12px; background: rgba(102, 126, 234, 0.1); border-radius: 8px; border-left: 3px solid #667eea;">
                    <div style="font-size: 0.85rem; color: #666; margin-bottom: 5px; font-weight: 600;">ZGOLD Fiyat Formülü:</div>
                    <div style="font-size: 0.9rem; color: #333; font-style: italic; margin-bottom: 8px;">
                        ZGOLD Fiyatı = (Altın karşılığı (gram)) × (Borsa İstanbul gram altın fiyatı)
                    </div>
                    <div style="font-size: 0.85rem; color: #666; margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(102, 126, 234, 0.2);">
                        <div style="margin-bottom: 3px;"><strong>Hesaplanan Altın Karşılığı:</strong> ${etf.gold_backing_grams.toFixed(6)} gram</div>
                        <div style="font-size: 0.8rem; color: #888; font-style: italic; margin-bottom: 5px;">
                            (ZGOLD Fiyatı ÷ Gram Altın Fiyatı)
                        </div>
                        <div style="color: #4CAF50; font-weight: 600;">Gram Başına Fiyat: ${formatPrice(etf.current_price / etf.gold_backing_grams)} TL/gram</div>
                    </div>
                </div>
                ` : etf.symbol === 'ZGOLD' ? `
                <div class="formula-info" style="margin-top: 15px; padding: 12px; background: rgba(102, 126, 234, 0.1); border-radius: 8px; border-left: 3px solid #667eea;">
                    <div style="font-size: 0.85rem; color: #666; margin-bottom: 5px; font-weight: 600;">ZGOLD Fiyat Formülü:</div>
                    <div style="font-size: 0.9rem; color: #333; font-style: italic;">
                        ZGOLD Fiyatı = (Altın karşılığı (gram)) × (Borsa İstanbul gram altın fiyatı)
                    </div>
                </div>
                ` : etf.symbol === 'GLDTR' && etf.gold_backing_grams ? `
                <div class="formula-info" style="margin-top: 15px; padding: 12px; background: rgba(255, 152, 0, 0.1); border-radius: 8px; border-left: 3px solid #FF9800;">
                    <div style="font-size: 0.85rem; color: #666; margin-bottom: 5px; font-weight: 600;">GLDTR Fiyat Formülü:</div>
                    <div style="font-size: 0.9rem; color: #333; font-style: italic; margin-bottom: 8px;">
                        GLDTR Fiyatı = NAV (Net Varlık Değeri) / Toplam Pay Sayısı
                        <br>
                        <span style="font-size: 0.85rem;">NAV = (Altın karşılığı × Uluslararası altın fiyatı × Dolar/TL kuru)</span>
                    </div>
                    <div style="font-size: 0.85rem; color: #666; margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(255, 152, 0, 0.2);">
                        <div style="margin-bottom: 3px;"><strong>Hesaplanan Altın Karşılığı:</strong> ${etf.gold_backing_grams.toFixed(6)} gram</div>
                        <div style="font-size: 0.8rem; color: #888; font-style: italic; margin-bottom: 5px;">
                            (GLDTR Fiyatı ÷ Gram Altın Fiyatı)
                        </div>
                        <div style="color: #4CAF50; font-weight: 600;">Gram Başına Fiyat: ${formatPrice(etf.current_price / etf.gold_backing_grams)} TL/gram</div>
                    </div>
                </div>
                ` : etf.symbol === 'GLDTR' ? `
                <div class="formula-info" style="margin-top: 15px; padding: 12px; background: rgba(255, 152, 0, 0.1); border-radius: 8px; border-left: 3px solid #FF9800;">
                    <div style="font-size: 0.85rem; color: #666; margin-bottom: 5px; font-weight: 600;">GLDTR Fiyat Formülü:</div>
                    <div style="font-size: 0.9rem; color: #333; font-style: italic;">
                        GLDTR Fiyatı = NAV (Net Varlık Değeri) / Toplam Pay Sayısı
                        <br>
                        <span style="font-size: 0.85rem;">NAV = (Altın karşılığı × Uluslararası altın fiyatı × Dolar/TL kuru)</span>
                    </div>
                </div>
                ` : ''}
            </div>
            <div class="etf-stats">
                ${isCheapest ? '<div style="font-size: 2rem;">🏆</div>' : ''}
            </div>
        `;
        
        etfList.appendChild(etfCard);
    });

    showResults();
}

function formatPrice(price) {
    return new Intl.NumberFormat('tr-TR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 4
    }).format(price);
}

function formatNumber(num) {
    return new Intl.NumberFormat('tr-TR').format(num);
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('tr-TR', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    }).format(date);
}

function showLoading() {
    loading.classList.remove('hidden');
}

function hideLoading() {
    loading.classList.add('hidden');
}

function showError(message) {
    error.textContent = message;
    error.classList.remove('hidden');
}

function hideError() {
    error.classList.add('hidden');
}

function showResults() {
    results.classList.remove('hidden');
}

function hideResults() {
    results.classList.add('hidden');
}


