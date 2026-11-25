// ============================================================================
// PULSEROUTE — ENTERPRISE BI CONTROLLER (Charcoal Slate & Warm Sand Theme)
// Author: Mohammed Zaidaan Shiraz
// ============================================================================

let currentTab = 'overview';
let currentRebalancePct = 15;
let lastCopilotResult = null;
let lastDashboardData = null;

const THEME = {
  charcoal: '#2C343D',
  slate: '#5A636C',
  taupe: '#9D9386',
  warmGray: '#C8C0B5',
  sandBeige: '#DFD8CE',
  textMain: '#1F2428',
  textSub: '#686E73'
};

const PLOTLY_CONFIG = { responsive: true, displayModeBar: false };

// Built-in Curated SQL Copilot Examples (Instant Zero-Latency Fallback + API Sync)
const DEFAULT_COPILOT_PRESETS = [
  {
    id: 'zone_sla_breach',
    badge: 'Q1 · ZONE SLA & GMV',
    concepts: 'JOIN · GROUP BY',
    question: 'Which delivery zones have the highest SLA breach rate and GMV at risk?',
    explanation: 'Aggregates SLA breaches and GMV exposure across geographic zones using an INNER JOIN between deliveries and cities.',
    sql: `SELECT
    c.zone AS Delivery_Zone,
    COUNT(d.order_id) AS Total_Orders,
    SUM(CASE WHEN d.calculated_sla_breach = 'Yes' THEN 1 ELSE 0 END) AS SLA_Breaches,
    ROUND(SUM(CASE WHEN d.calculated_sla_breach = 'Yes' THEN 1.0 ELSE 0.0 END) * 100.0 / COUNT(d.order_id), 2) AS SLA_Breach_Rate_Pct,
    ROUND(AVG(d.calculated_delay_days), 2) AS Avg_Delay_Days,
    ROUND(SUM(CASE WHEN d.calculated_sla_breach = 'Yes' THEN d.order_value_inr ELSE 0 END), 0) AS GMV_At_Risk_INR
FROM deliveries d
JOIN cities c ON d.city_id = c.city_id
GROUP BY c.zone
ORDER BY SLA_Breach_Rate_Pct DESC;`
  },
  {
    id: 'vendor_benchmark',
    badge: 'Q2 · 3PL BENCHMARK',
    concepts: 'CTE · DENSE_RANK()',
    question: 'Rank all 3PL carriers by SLA breach rate vs network average using a CTE.',
    explanation: 'Uses a Common Table Expression (CTE) + DENSE_RANK() window function to benchmark each 3PL partner against the network average SLA breach rate.',
    sql: `WITH vendor_kpis AS (
    SELECT
        v.vendor_name AS Carrier,
        COUNT(d.order_id) AS Total_Dispatches,
        ROUND(AVG(d.delivery_lead_time_days), 2) AS Avg_Cycle_Days,
        ROUND(SUM(CASE WHEN d.calculated_sla_breach = 'Yes' THEN 1.0 ELSE 0.0 END) * 100.0 / COUNT(d.order_id), 2) AS Breach_Rate_Pct
    FROM deliveries d
    JOIN vendors v ON d.vendor_id = v.vendor_id
    GROUP BY v.vendor_name
),
network_avg AS (
    SELECT ROUND(AVG(Breach_Rate_Pct), 2) AS Net_Breach_Pct FROM vendor_kpis
)
SELECT
    vk.Carrier,
    vk.Total_Dispatches,
    vk.Avg_Cycle_Days,
    vk.Breach_Rate_Pct,
    na.Net_Breach_Pct AS Network_Avg_Pct,
    ROUND(vk.Breach_Rate_Pct - na.Net_Breach_Pct, 2) AS Variance_vs_Network_Pts,
    DENSE_RANK() OVER (ORDER BY vk.Breach_Rate_Pct ASC) AS Reliability_Rank
FROM vendor_kpis vk
CROSS JOIN network_avg na
ORDER BY Reliability_Rank ASC;`
  },
  {
    id: 'city_pareto_defects',
    badge: 'Q3 · CITY PARETO 80/20',
    concepts: 'SUM() OVER ()',
    question: 'Which top 10 cities contribute the largest share of delayed shipments (Pareto analysis)?',
    explanation: 'Applies a window aggregation SUM(COUNT(*)) OVER () to compute each citys exact percentage contribution to total network delays.',
    sql: `SELECT
    c.city_name AS City,
    c.zone AS Zone,
    COUNT(d.order_id) AS Delayed_Orders,
    ROUND(COUNT(d.order_id) * 100.0 / SUM(COUNT(d.order_id)) OVER (), 2) AS Share_Of_Network_Delays_Pct,
    ROUND(AVG(d.calculated_delay_days), 2) AS Avg_Delay_Days
FROM deliveries d
JOIN cities c ON d.city_id = c.city_id
WHERE d.calculated_delivery_status = 'Delayed'
GROUP BY c.city_name, c.zone
ORDER BY Delayed_Orders DESC
LIMIT 10;`
  },
  {
    id: 'root_cause_pareto',
    badge: 'Q4 · ROOT CAUSE AUDIT',
    concepts: 'LEFT JOIN · WINDOW',
    question: 'What are the primary root causes of delivery delays and SLA breaches?',
    explanation: 'Summarizes true delayed shipments by root cause and category, quantifying both delay frequency and severe (>2 days) SLA breaches.',
    sql: `SELECT
    COALESCE(dr.reason_name, 'Not Recorded') AS Delay_Root_Cause,
    COALESCE(dr.reason_category, 'Operational') AS Reason_Category,
    COUNT(d.order_id) AS Delayed_Shipments,
    SUM(CASE WHEN d.calculated_sla_breach = 'Yes' THEN 1 ELSE 0 END) AS Severe_SLA_Breaches,
    ROUND(COUNT(d.order_id) * 100.0 / SUM(COUNT(d.order_id)) OVER (), 2) AS Share_Of_Delays_Pct,
    ROUND(AVG(d.calculated_delay_days), 2) AS Avg_Delay_When_Triggered
FROM deliveries d
LEFT JOIN delay_reasons dr ON d.reason_id = dr.reason_id
WHERE d.calculated_delivery_status = 'Delayed'
GROUP BY Delay_Root_Cause, Reason_Category
ORDER BY Delayed_Shipments DESC;`
  },
  {
    id: 'data_quality_forensics',
    badge: 'Q5 · DATA FORENSICS',
    concepts: 'CASE RECONCILIATION',
    question: 'Show the forensic breakdown of legacy data-quality discrepancies across the 5,200 records.',
    explanation: 'Audits the exact counts of legacy logging errors: 252 delayed date mismatches, 99 SLA rule contradictions, and 233 phantom delays with NULL reasons.',
    sql: `SELECT
    SUM(CASE WHEN is_delayed_raw = 'Yes' AND delay_days_raw != calculated_delay_days THEN 1 ELSE 0 END) AS Delayed_Date_Math_Mismatches_252,
    SUM(CASE WHEN (delay_days_raw > 2 AND sla_breached_raw = 'No') OR (delay_days_raw <= 2 AND sla_breached_raw = 'Yes') THEN 1 ELSE 0 END) AS Legacy_SLA_Rule_Mismatches_99,
    SUM(CASE WHEN is_delayed_raw = 'Yes' AND reason_id IS NULL THEN 1 ELSE 0 END) AS Missing_Delay_Reasons_233,
    SUM(CASE WHEN delay_days_raw != calculated_delay_days THEN 1 ELSE 0 END) AS Total_Raw_Delay_Capped_Mismatches_1723,
    COUNT(*) AS Total_Audited_Records
FROM deliveries;`
  },
  {
    id: 'seasonal_monsoon_cod',
    badge: 'Q6 · MONSOON × COD',
    concepts: 'MULTI-DIM GROUP BY',
    question: 'How do Monsoon weather and COD payment modes impact SLA breach rates and delivery attempts?',
    explanation: 'Cross-tabulates Monsoon vs Non-Monsoon dispatches across COD and Prepaid orders to isolate weather and payment-collection friction.',
    sql: `SELECT
    is_monsoon_season AS Monsoon_Season,
    payment_mode AS Payment_Mode,
    COUNT(order_id) AS Orders,
    ROUND(AVG(delivery_attempts), 2) AS Avg_Delivery_Attempts,
    ROUND(SUM(CASE WHEN calculated_sla_breach = 'Yes' THEN 1.0 ELSE 0.0 END) * 100.0 / COUNT(order_id), 2) AS SLA_Breach_Rate_Pct,
    ROUND(AVG(calculated_delay_days), 2) AS Avg_Delay_Days
FROM deliveries
GROUP BY is_monsoon_season, payment_mode
ORDER BY SLA_Breach_Rate_Pct DESC;`
  },
  {
    id: 'mom_trend_lag',
    badge: 'Q7 · MONTHLY LAG()',
    concepts: 'CTE · LAG() OVER',
    question: 'What is the month-over-month (MoM) order volume and SLA breach rate change using LAG()?',
    explanation: 'Uses the LAG() window function over monthly cohorts to track sequential volume growth and SLA breach rate drift.',
    sql: `WITH monthly_stats AS (
    SELECT
        SUBSTR(order_date, 1, 7) AS Order_Month,
        COUNT(order_id) AS Total_Orders,
        ROUND(SUM(CASE WHEN calculated_sla_breach = 'Yes' THEN 1.0 ELSE 0.0 END) * 100.0 / COUNT(order_id), 2) AS Breach_Rate_Pct
    FROM deliveries
    GROUP BY SUBSTR(order_date, 1, 7)
)
SELECT
    Order_Month,
    Total_Orders,
    LAG(Total_Orders) OVER (ORDER BY Order_Month) AS Prev_Month_Orders,
    Breach_Rate_Pct,
    LAG(Breach_Rate_Pct) OVER (ORDER BY Order_Month) AS Prev_Month_Breach_Pct,
    ROUND(Breach_Rate_Pct - LAG(Breach_Rate_Pct) OVER (ORDER BY Order_Month), 2) AS MoM_Breach_Delta_Pts
FROM monthly_stats
ORDER BY Order_Month ASC;`
  }
];

let copilotPresets = [...DEFAULT_COPILOT_PRESETS];

function fmtINRCompact(num) {
  if (num === null || num === undefined) return '—';
  const n = Number(num);
  if (n >= 10000000) return '₹' + (n / 10000000).toFixed(2) + 'Cr';
  if (n >= 1000000) return '₹' + (n / 1000000).toFixed(2) + 'M';
  if (n >= 1000) return '₹' + (n / 1000).toFixed(1) + 'K';
  return '₹' + n.toLocaleString('en-IN');
}

function fmtINR(num) {
  if (num === null || num === undefined) return '—';
  return '₹' + Number(num).toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

function getActiveFilterParams() {
  return {
    zone: (document.getElementById('filter-zone') || {}).value || 'All',
    city: (document.getElementById('filter-city') || {}).value || 'All',
    vendor: (document.getElementById('filter-vendor') || {}).value || 'All',
    category: (document.getElementById('filter-category') || {}).value || 'All',
    payment_mode: (document.getElementById('filter-payment') || {}).value || 'All',
    season: (document.getElementById('filter-season') || {}).value || 'All',
    rebalance_pct: currentRebalancePct
  };
}

// ----------------------------------------------------------------------------
// TAB NAVIGATION & QUICK SLICERS
// ----------------------------------------------------------------------------
const VIEW_TITLES = {
  overview: 'Delivery Operations Overview',
  forensics: 'Forensic Data Quality Audit (252 / 99 / 233)',
  rebalance: '3PL Carrier Rebalancing Simulator',
  copilot: 'Read-Only SQL & Analytics Copilot',
  anomalies: '6-Month Demand Forecast & Outlier Radar'
};

function switchTab(tabId) {
  currentTab = tabId;
  const tabs = ['overview', 'forensics', 'rebalance', 'copilot', 'anomalies'];
  tabs.forEach(t => {
    const el = document.getElementById(`tab-${t}`);
    const btn = document.getElementById(`tab-btn-${t}`);
    if (el && btn) {
      if (t === tabId) {
        el.classList.remove('hidden');
        btn.classList.add('active');
      } else {
        el.classList.add('hidden');
        btn.classList.remove('active');
      }
    }
  });

  const titleEl = document.getElementById('header-view-title');
  if (titleEl && VIEW_TITLES[tabId]) {
    titleEl.textContent = VIEW_TITLES[tabId];
  }

  if (tabId === 'forensics') {
    loadDataQualityForensics();
  } else if (tabId === 'anomalies') {
    loadAnomaliesAndForecast();
  } else if (tabId === 'overview' && lastDashboardData) {
    renderOverviewCharts(lastDashboardData);
  }
  window.dispatchEvent(new Event('resize'));
}

function setQuickSeason(val, btnEl) {
  const input = document.getElementById('filter-season');
  if (input) input.value = val;

  document.querySelectorAll('.season-pill').forEach(b => {
    const isMatch = b === btnEl || b.getAttribute('data-season') === val;
    b.classList.toggle('active', isMatch);
  });

  const tagEl = document.getElementById('sidebar-season-tag');
  if (tagEl) tagEl.textContent = val;

  triggerAllActiveViewsRefresh();
}

function setQuickPayment(val, btnEl) {
  const input = document.getElementById('filter-payment');
  if (input) input.value = val;

  document.querySelectorAll('.payment-pill').forEach(b => {
    const isMatch = b === btnEl || b.getAttribute('data-payment') === val;
    b.classList.toggle('active', isMatch);
  });

  const tagEl = document.getElementById('sidebar-payment-tag');
  if (tagEl) tagEl.textContent = val;

  triggerAllActiveViewsRefresh();
}

function onDimensionSlicerChange() {
  triggerAllActiveViewsRefresh();
}

async function triggerAllActiveViewsRefresh() {
  await refreshDashboard();
  if (currentTab === 'forensics') {
    await loadDataQualityForensics();
  } else if (currentTab === 'anomalies') {
    await loadAnomaliesAndForecast();
  } else if (currentTab === 'copilot') {
    await runFilteredCopilotSliceQuery();
  }
}

// When the user clicks a sidebar slicer while viewing the SQL Copilot tab,
// synthesize and execute a live read-only SQL query reflecting that exact slice!
async function runFilteredCopilotSliceQuery() {
  const f = getActiveFilterParams();
  const clauses = [];
  if (f.zone !== 'All') clauses.push(`c.zone = '${f.zone.replace(/'/g, "''")}'`);
  if (f.city !== 'All') clauses.push(`c.city_name = '${f.city.replace(/'/g, "''")}'`);
  if (f.vendor !== 'All') clauses.push(`v.vendor_name = '${f.vendor.replace(/'/g, "''")}'`);
  if (f.category !== 'All') clauses.push(`d.product_category = '${f.category.replace(/'/g, "''")}'`);
  if (f.payment_mode !== 'All') clauses.push(`d.payment_mode = '${f.payment_mode.replace(/'/g, "''")}'`);
  if (f.season === 'Monsoon') clauses.push(`d.is_monsoon_season = 'Yes'`);
  if (f.season === 'Festive') clauses.push(`d.is_festive_season = 'Yes'`);
  if (f.season === 'Normal') clauses.push(`d.is_monsoon_season = 'No' AND d.is_festive_season = 'No'`);

  const whereSQL = clauses.length > 0 ? `\nWHERE ${clauses.join(' AND ')}` : '';
  const dynamicSQL = `SELECT
    c.zone AS Delivery_Zone,
    v.vendor_name AS Carrier,
    COUNT(d.order_id) AS Dispatches,
    SUM(CASE WHEN d.calculated_sla_breach = 'Yes' THEN 1 ELSE 0 END) AS SLA_Breaches,
    ROUND(SUM(CASE WHEN d.calculated_sla_breach = 'Yes' THEN 1.0 ELSE 0.0 END) * 100.0 / COUNT(d.order_id), 2) AS Breach_Rate_Pct,
    ROUND(AVG(d.delivery_lead_time_days), 2) AS Avg_Lead_Days,
    ROUND(SUM(d.order_value_inr), 0) AS Cohort_GMV_INR
FROM deliveries d
JOIN cities c ON d.city_id = c.city_id
JOIN vendors v ON d.vendor_id = v.vendor_id${whereSQL}
GROUP BY c.zone, v.vendor_name
ORDER BY Breach_Rate_Pct DESC
LIMIT 15;`;

  const desc = clauses.length > 0 ? `Filtered SQL Slice (${clauses.join(', ')})` : 'Full Network SQL Slice (All 5,200 Dispatches)';
  const qInput = document.getElementById('copilot-question');
  if (qInput) qInput.value = `Analyze SLA breach rate for active sidebar slice: ${desc}`;
  await executeCopilotRequest(`Analyze SLA breach rate for active sidebar slice: ${desc}`, dynamicSQL);
}

// ----------------------------------------------------------------------------
// INITIALIZATION & FILTER LOADING
// ----------------------------------------------------------------------------
async function initApp() {
  try {
    if (window.lucide) lucide.createIcons();
  } catch (e) {
    console.warn('Lucide icon init skipped:', e);
  }

  try {
    await loadFilters();
  } catch (e) {
    console.error('Filter load error:', e);
  }

  try {
    await refreshDashboard();
  } catch (e) {
    console.error('Dashboard refresh error:', e);
  }

  try {
    await loadCopilotPresets();
  } catch (e) {
    console.error('Copilot presets load error:', e);
  }
}

async function loadFilters() {
  const res = await fetch('/api/filters');
  const data = await res.json();

  populateSelect('filter-zone', 'Zone', data.zones);
  populateSelect('filter-city', 'City', data.cities);
  populateSelect('filter-vendor', 'Carrier', data.vendors);
  populateSelect('filter-category', 'Category', data.categories);
}

function populateSelect(id, labelPrefix, options) {
  const sel = document.getElementById(id);
  if (!sel || !Array.isArray(options)) return;
  const currentVal = sel.value || 'All';
  sel.innerHTML = options.map(o => `<option value="${o}">${o === 'All' ? `${labelPrefix}: All` : `${labelPrefix}: ${o}`}</option>`).join('');
  if (options.includes(currentVal)) {
    sel.value = currentVal;
  }
}

function resetFilters() {
  ['filter-zone', 'filter-city', 'filter-vendor', 'filter-category'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = 'All';
  });
  const sEl = document.getElementById('filter-season');
  if (sEl) sEl.value = 'All';
  const pEl = document.getElementById('filter-payment');
  if (pEl) pEl.value = 'All';

  const sTag = document.getElementById('sidebar-season-tag');
  if (sTag) sTag.textContent = 'All';
  const pTag = document.getElementById('sidebar-payment-tag');
  if (pTag) pTag.textContent = 'All';

  document.querySelectorAll('.season-pill').forEach((b, i) => b.classList.toggle('active', i === 0));
  document.querySelectorAll('.payment-pill').forEach((b, i) => b.classList.toggle('active', i === 0));

  triggerAllActiveViewsRefresh();
}

function onSliderChange(val) {
  currentRebalancePct = Number(val);
  const label = document.getElementById('sim-slider-val');
  if (label) label.textContent = `${val}%`;
  refreshDashboard();
}

// ----------------------------------------------------------------------------
// MINI SPARKLINE RENDERER (FOR TOP 5 KPI CARDS)
// ----------------------------------------------------------------------------
function renderMiniSparkline(divId, values) {
  if (!values || !values.length || !window.Plotly) return;
  const el = document.getElementById(divId);
  if (!el) return;
  const x = values.map((_, i) => i);
  const maxIdx = values.indexOf(Math.max(...values));
  const minIdx = values.indexOf(Math.min(...values));

  Plotly.newPlot(divId, [
    {
      x,
      y: values,
      type: 'scatter',
      mode: 'lines',
      fill: 'tozeroy',
      line: { color: '#5A636C', width: 1.5 },
      fillcolor: 'rgba(157, 147, 134, 0.38)',
      hoverinfo: 'skip'
    },
    {
      x: [minIdx, maxIdx],
      y: [values[minIdx], values[maxIdx]],
      type: 'scatter',
      mode: 'markers',
      marker: { color: '#1F2428', size: 4.5 },
      hoverinfo: 'skip'
    }
  ], {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    margin: { t: 4, r: 4, b: 4, l: 4 },
    xaxis: { visible: false },
    yaxis: { visible: false },
    showlegend: false
  }, PLOTLY_CONFIG);
}

// ----------------------------------------------------------------------------
// DASHBOARD REFRESH
// ----------------------------------------------------------------------------
async function refreshDashboard() {
  const f = getActiveFilterParams();
  const params = new URLSearchParams(f);

  const res = await fetch(`/api/dashboard?${params.toString()}`);
  const data = await res.json();

  // Update Live Filter Scope Badge in Header & Sidebar
  const activeTags = [];
  if (f.season !== 'All') activeTags.push(`Season: ${f.season}`);
  if (f.payment_mode !== 'All') activeTags.push(`Mode: ${f.payment_mode}`);
  if (f.zone !== 'All') activeTags.push(`Zone: ${f.zone}`);
  if (f.city !== 'All') activeTags.push(`City: ${f.city}`);
  if (f.vendor !== 'All') activeTags.push(`Carrier: ${f.vendor}`);
  if (f.category !== 'All') activeTags.push(`Cat: ${f.category}`);

  const matchedCount = data.empty ? 0 : data.kpis.total_orders;
  const scopeText = activeTags.length > 0
    ? `Filtered (${activeTags.join(' · ')}) · ${matchedCount.toLocaleString()} / 5,200 Dispatches`
    : `Scope: All Seasons · All Modes · ${matchedCount.toLocaleString()} / 5,200 Dispatches`;

  const badgeEl = document.getElementById('header-filter-badge');
  if (badgeEl) badgeEl.textContent = scopeText;

  const sideCountEl = document.getElementById('sidebar-matched-count');
  if (sideCountEl) sideCountEl.textContent = `${matchedCount.toLocaleString()} rows`;

  if (data.empty) return;
  lastDashboardData = data;

  const k = data.kpis;
  const m = data.monthly_trend || [];

  // Populate Top 5 KPI Cards
  document.getElementById('kpi-total').textContent = k.total_orders.toLocaleString();
  document.getElementById('kpi-total-bm').textContent = `${(k.early_orders + k.on_time_orders).toLocaleString()} On-Time`;
  document.getElementById('kpi-total-delta').textContent = `▲ ${k.delayed_orders.toLocaleString()} Delayed`;

  document.getElementById('kpi-gmv').textContent = fmtINRCompact(k.total_gmv_inr);
  document.getElementById('kpi-gmv-bm').textContent = fmtINRCompact(k.gmv_at_risk_inr);
  const protectedPct = k.total_gmv_inr > 0 ? ((1 - k.gmv_at_risk_inr / k.total_gmv_inr) * 100).toFixed(1) : '0.0';
  document.getElementById('kpi-gmv-delta').textContent = `▲ ${protectedPct}% Safe`;

  document.getElementById('kpi-lead').textContent = `${k.avg_lead_time.toFixed(2)} d`;
  document.getElementById('kpi-lead-bm').textContent = `${k.avg_promised_time.toFixed(2)} d`;
  document.getElementById('kpi-lead-delta').textContent = `+${k.avg_delay_when_delayed.toFixed(2)} d Late`;

  document.getElementById('kpi-ontime').textContent = `${k.on_time_rate.toFixed(2)}%`;
  const ontimeVar = (k.on_time_rate - 70.0).toFixed(2);
  const ontimeEl = document.getElementById('kpi-ontime-delta');
  ontimeEl.textContent = `${ontimeVar >= 0 ? '▲ +' : '▼ '}${ontimeVar}%`;
  ontimeEl.className = ontimeVar >= 0 ? 'delta-pos mt-0.5' : 'delta-neg mt-0.5';

  document.getElementById('kpi-breach').textContent = `${k.sla_breach_rate.toFixed(2)}%`;
  document.getElementById('kpi-breach-delta').textContent = `▲ ${k.sla_breaches.toLocaleString()} Orders`;

  // Render Top 5 Sparklines
  if (m.length > 0) {
    renderMiniSparkline('spark-1', m.map(r => r.orders));
    renderMiniSparkline('spark-2', m.map(r => r.gmv));
    renderMiniSparkline('spark-3', m.map(r => r.delayed));
    renderMiniSparkline('spark-4', m.map(r => r.on_time_rate));
    renderMiniSparkline('spark-5', m.map(r => r.breach_rate));
  }

  // Row 2 Right: Root Cause Horizontal Bars
  const rcList = (data.root_causes || []).slice(0, 4);
  const maxRc = rcList.length ? Math.max(...rcList.map(r => r.delayed_orders)) : 1;
  const rcColors = ['#2C343D', '#6E685F', '#9D9386', '#B8B0A4'];
  document.getElementById('root-cause-bars').innerHTML = rcList.map((r, i) => {
    const pct = Math.max(22, Math.round((r.delayed_orders / maxRc) * 100));
    const shortName = r.reason.replace(' Failure', '').replace(' Delay', '');
    return `
      <div class="grid grid-cols-12 items-center gap-2 text-[11px]">
        <div class="col-span-5 font-medium text-[#1F2428] truncate" title="${r.reason}">${shortName}</div>
        <div class="col-span-7 bg-[#E2DDD5] rounded-md h-6 overflow-hidden flex items-center">
          <div style="width:${pct}%; background-color:${rcColors[i % rcColors.length]};" class="h-full rounded-md flex items-center justify-end px-2 text-[10px] font-mono font-semibold text-white">
            ${r.delayed_orders}
          </div>
        </div>
      </div>
    `;
  }).join('');

  // Row 3 Left: City Hub Details Table
  const topCities = (data.cities || []).slice(0, 6);
  document.getElementById('city-hub-tbody').innerHTML = topCities.map((c, idx) => `
    <tr class="hover:bg-[#EAE5DE] transition">
      <td class="py-1.5 px-2 font-mono font-semibold text-[#1F2428] flex items-center gap-1.5">
        <span class="w-4 h-4 rounded-full bg-[#2C343D] text-white text-[9px] flex items-center justify-center font-bold">${idx + 1}</span>
        HUB00${idx + 1}
      </td>
      <td class="py-1.5 px-2 text-[#323A45] font-medium">${c.City} <span class="text-[#686E73]">(${c.Zone})</span></td>
      <td class="py-1.5 px-2 text-right font-mono">${c.orders}</td>
      <td class="py-1.5 px-2 text-right font-mono font-semibold">${c.delayed}</td>
      <td class="py-1.5 px-2 text-right font-mono font-bold text-[#1F2428]">${c.breach_rate.toFixed(1)}%</td>
    </tr>
  `).join('');

  // Row 3 Center: Carrier Horizontal Pill Bars
  const vSorted = [...(data.vendors || [])].sort((a, b) => b.breach_rate - a.breach_rate).slice(0, 6);
  const maxBr = vSorted.length ? Math.max(...vSorted.map(v => v.breach_rate)) : 1;
  const barShades = ['#2C343D', '#4A525A', '#686E73', '#7E7870', '#968E83', '#ACA499'];
  document.getElementById('carrier-pill-bars').innerHTML = vSorted.map((v, i) => {
    const wPct = Math.max(30, Math.round((v.breach_rate / maxBr) * 100));
    return `
      <div class="grid grid-cols-12 items-center gap-2 text-[11px]">
        <div class="col-span-4 font-semibold text-[#1F2428] truncate">${v.Vendor}</div>
        <div class="col-span-8 flex items-center">
          <div style="width:${wPct}%; background-color:${barShades[i % barShades.length]};" class="h-5 rounded-full flex items-center justify-end px-2.5 text-[10px] font-mono font-semibold text-white">
            ${v.breach_rate.toFixed(1)}%
          </div>
        </div>
      </div>
    `;
  }).join('');

  // Rebalance Simulation KPIs (Tab 3)
  const sim = data.rebalance_simulation;
  document.getElementById('sim-shifted').textContent = `${sim.shifted_orders.toLocaleString()} orders`;
  document.getElementById('sim-avoided').textContent = `${sim.breaches_avoided.toLocaleString()} breaches saved`;
  document.getElementById('sim-new-rate').textContent = `${sim.projected_breach_rate.toFixed(2)}% (-${sim.bps_improvement} bps)`;
  document.getElementById('sim-gmv').textContent = fmtINR(sim.gmv_protected_inr);

  // Carrier League Table (Tab 3)
  document.getElementById('vendor-league-body').innerHTML = (data.vendors || []).map((v, idx) => `
    <tr class="hover:bg-[#EAE5DE]">
      <td class="py-2 px-3 font-bold text-[#686E73]">#${idx + 1}</td>
      <td class="py-2 px-3 font-bold text-[#1F2428]">${v.Vendor}</td>
      <td class="py-2 px-3">${v.orders.toLocaleString()}</td>
      <td class="py-2 px-3 text-[#2B6E46] font-bold">${v.on_time_rate.toFixed(1)}%</td>
      <td class="py-2 px-3 text-[#A63A3A] font-bold">${v.breach_rate.toFixed(1)}%</td>
      <td class="py-2 px-3">${v.avg_lead_time.toFixed(2)} d</td>
      <td class="py-2 px-3">${fmtINR(v.gmv)}</td>
    </tr>
  `).join('');

  renderOverviewCharts(data);
}

// ----------------------------------------------------------------------------
// OVERVIEW CHARTS
// ----------------------------------------------------------------------------
function renderOverviewCharts(data) {
  if (!window.Plotly) return;
  const k = data.kpis;
  const minorDelay = Math.max(0, k.delayed_orders - k.sla_breaches);

  // 1. Row 2 Left: 3-Column Bar Chart with Center Dark Slate Bar
  const xLabels = ['Early (<0d)', 'On-Time / Minor (0-2d)', 'SLA Breached (>2d)'];
  const yVals = [k.early_orders, k.on_time_orders + minorDelay, k.sla_breaches];
  const barColors = ['#DFD8CE', '#2C343D', '#C8C0B5'];
  const textColors = ['#1F2428', '#FFFFFF', '#1F2428'];

  Plotly.newPlot('chart-status-columns', [
    {
      x: xLabels,
      y: yVals,
      type: 'bar',
      text: yVals.map(v => v.toLocaleString()),
      textposition: 'inside',
      insidetextanchor: 'start',
      textfont: { family: 'Inter, sans-serif', size: 11, color: textColors, weight: 'bold' },
      marker: {
        color: barColors,
        line: { color: '#B8B0A4', width: 1 }
      },
      width: [0.52, 0.52, 0.52]
    }
  ], {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { family: 'Inter, sans-serif', color: THEME.textMain, size: 11 },
    margin: { t: 12, r: 12, b: 28, l: 12 },
    xaxis: { showgrid: false, zeroline: false },
    yaxis: { visible: false }
  }, PLOTLY_CONFIG);

  // 2. Row 2 Center: Geographic Zone Donut Chart
  const zones = data.zones || [];
  Plotly.newPlot('chart-zone-donut', [
    {
      labels: zones.map(z => z.Zone),
      values: zones.map(z => z.orders),
      type: 'pie',
      hole: 0.48,
      marker: {
        colors: ['#2C343D', '#5A636C', '#8C8275', '#B8B0A4', '#D5CFC7'],
        line: { color: '#F3EFEA', width: 2 }
      },
      textinfo: 'label+percent',
      textposition: 'outside',
      automargin: true,
      textfont: { size: 10.5, color: THEME.textMain }
    }
  ], {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    margin: { t: 10, r: 20, b: 10, l: 20 },
    showlegend: false
  }, PLOTLY_CONFIG);

  // 3. Row 3 Right: SLA Compliance Breakdown Donut
  Plotly.newPlot('chart-sla-donut', [
    {
      labels: ['Early', 'On-Time', 'SLA Breached'],
      values: [k.early_orders, k.on_time_orders + minorDelay, k.sla_breaches],
      type: 'pie',
      hole: 0.52,
      marker: {
        colors: ['#2C343D', '#8C8275', '#C8C0B5'],
        line: { color: '#F3EFEA', width: 2 }
      },
      textinfo: 'percent',
      textposition: 'outside',
      automargin: true,
      textfont: { size: 10.5, color: THEME.textMain }
    }
  ], {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    margin: { t: 8, r: 16, b: 36, l: 16 },
    showlegend: true,
    legend: { orientation: 'h', y: -0.15, x: 0.5, xanchor: 'center', font: { size: 10, color: THEME.textMain } }
  }, PLOTLY_CONFIG);
}

// ----------------------------------------------------------------------------
// DATA QUALITY FORENSICS LOADER
// ----------------------------------------------------------------------------
async function loadDataQualityForensics() {
  const params = new URLSearchParams(getActiveFilterParams());
  const res = await fetch(`/api/data-quality?${params.toString()}`);
  const data = await res.json();

  const s = data.summary;
  document.getElementById('dq-count-252').textContent = s.delayed_date_mismatches_252.toLocaleString();
  document.getElementById('dq-count-99').textContent = s.sla_rule_mismatches_99.toLocaleString();
  document.getElementById('dq-count-233').textContent = s.missing_delay_reasons_233.toLocaleString();
  document.getElementById('dq-count-1723').textContent = s.raw_early_capped_mismatches_1723.toLocaleString();

  const tbody = document.getElementById('dq-table-body');
  tbody.innerHTML = data.sample_reconciled_records.map(r => `
    <tr class="hover:bg-[#EAE5DE]">
      <td class="py-2 px-3 font-bold text-[#1F2428]">${r.Order_ID}</td>
      <td class="py-2 px-3">${r.City} · <span class="text-[#686E73]">${r.Vendor}</span></td>
      <td class="py-2 px-3">${r.Promised_Delivery_Date} → ${r.Actual_Delivery_Date}</td>
      <td class="py-2 px-3 text-[#A63A3A] font-bold">${r.Delay_Days} d</td>
      <td class="py-2 px-3 text-[#2B6E46] font-bold">${r.Calculated_Delay_Days} d</td>
      <td class="py-2 px-3 text-[#A63A3A]">Is_Delayed=${r.Is_Delayed}</td>
      <td class="py-2 px-3 text-[#2B6E46] font-bold">${r.Calculated_Delivery_Status}</td>
      <td class="py-2 px-3">${r.SLA_Breached} → <strong>${r.Calculated_SLA_Breach}</strong></td>
      <td class="py-2 px-3">${r.Delay_Reason} → <strong>${r.Cleaned_Delay_Reason}</strong></td>
    </tr>
  `).join('');
}

// ----------------------------------------------------------------------------
// READ-ONLY AI SQL COPILOT
// ----------------------------------------------------------------------------
async function loadCopilotPresets() {
  try {
    const res = await fetch('/api/copilot/presets');
    const data = await res.json();
    if (data.presets && data.presets.length > 0) {
      copilotPresets = data.presets.map((p, idx) => ({
        ...DEFAULT_COPILOT_PRESETS[idx],
        ...p
      }));
    }
  } catch (e) {
    console.warn('Using built-in SQL Copilot presets:', e);
  }

  renderCopilotPresetCards(0);
  await selectCopilotPreset(0);
}

function renderCopilotPresetCards(activeIdx) {
  const list = document.getElementById('copilot-presets-list');
  if (!list) return;
  list.innerHTML = copilotPresets.map((p, idx) => `
    <button type="button" onclick="selectCopilotPreset(${idx})" id="copilot-card-${idx}" class="copilot-example-card ${idx === activeIdx ? 'active' : ''} w-full text-left p-2.5 space-y-1">
      <div class="flex items-center justify-between text-[10px] font-mono opacity-80">
        <span class="font-bold">${p.badge || `Q${idx + 1}`}</span>
        <span>${p.concepts || 'READ-ONLY SQL'}</span>
      </div>
      <div class="text-xs font-bold">${p.question}</div>
      <div class="text-[10px] opacity-75">${p.explanation || ''}</div>
    </button>
  `).join('');
}

async function selectCopilotPreset(idx) {
  const p = copilotPresets[idx] || DEFAULT_COPILOT_PRESETS[idx];
  if (!p) return;

  copilotPresets.forEach((_, i) => {
    const card = document.getElementById(`copilot-card-${i}`);
    if (card) card.classList.toggle('active', i === idx);
  });

  const qEl = document.getElementById('copilot-question');
  if (qEl) qEl.value = p.question;

  const sqlEl = document.getElementById('copilot-sql-editor');
  if (sqlEl) sqlEl.value = p.sql;

  await executeCopilotRequest(p.question, p.sql);
}

async function askCopilotFromInput() {
  const q = document.getElementById('copilot-question').value.trim();
  if (!q) return;
  await executeCopilotRequest(q, null);
}

async function runCustomSQL() {
  const sql = document.getElementById('copilot-sql-editor').value.trim();
  const q = document.getElementById('copilot-question').value.trim();
  await executeCopilotRequest(q, sql);
}

async function testGuardrailAttack() {
  const attackSQL = "DROP TABLE deliveries;";
  document.getElementById('copilot-sql-editor').value = attackSQL;
  await executeCopilotRequest("Attempt destructive SQL injection", attackSQL);
}

async function executeCopilotRequest(question, custom_sql) {
  const apiKeyEl = document.getElementById('copilot-api-key');
  const api_key = apiKeyEl ? apiKeyEl.value.trim() : '';

  const res = await fetch('/api/copilot/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, custom_sql, api_key })
  });
  const data = await res.json();
  lastCopilotResult = data;

  document.getElementById('copilot-sql-editor').value = data.sql || '';
  document.getElementById('copilot-active-title').textContent = `${data.canonical_question || 'Custom Read-Only SQL Query'} [${data.engine_mode || 'Read-Only Engine'}]`;
  document.getElementById('copilot-active-desc').textContent = data.explanation || '';

  const banner = document.getElementById('copilot-status-banner');
  if (data.valid) {
    banner.className = 'rounded p-2.5 text-xs font-mono border bg-[#DCE8DF] border-[#B8D0BF] text-[#1E4D30]';
    banner.innerHTML = `<strong>[READ-ONLY GUARDRAIL PASSED · ${data.engine_mode || 'SQLite ?mode=ro'}]</strong> ${data.summary}`;
  } else {
    banner.className = 'rounded p-2.5 text-xs font-mono border bg-[#EAD8D8] border-[#D6B8B8] text-[#8B2626]';
    banner.innerHTML = `<strong>[SECURITY GUARDRAIL BLOCKED QUERY]</strong> ${data.status_message}`;
  }

  const thead = document.getElementById('copilot-table-head');
  const tbody = document.getElementById('copilot-table-body');

  if (!data.valid || !data.columns || data.columns.length === 0) {
    thead.innerHTML = '';
    tbody.innerHTML = '';
    return;
  }

  thead.innerHTML = `<tr>${data.columns.map(c => `<th class="py-2 px-3">${c}</th>`).join('')}</tr>`;
  tbody.innerHTML = data.rows.map(row => `
    <tr class="hover:bg-[#EAE5DE]">
      ${data.columns.map(c => `<td class="py-2 px-3 text-[#1F2428]">${row[c] !== null && row[c] !== undefined ? row[c] : 'NULL'}</td>`).join('')}
    </tr>
  `).join('');
}

function exportCopilotCSV() {
  if (!lastCopilotResult || !lastCopilotResult.valid || !lastCopilotResult.rows || !lastCopilotResult.rows.length) return;
  const cols = lastCopilotResult.columns;
  const lines = [
    cols.join(','),
    ...lastCopilotResult.rows.map(r => cols.map(c => `"${String(r[c] ?? '').replace(/"/g, '""')}"`).join(','))
  ];
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'pulseroute_copilot_query_export.csv';
  a.click();
}

// ----------------------------------------------------------------------------
// ANOMALIES & 6M FORECAST LOADER
// ----------------------------------------------------------------------------
async function loadAnomaliesAndForecast() {
  const params = new URLSearchParams(getActiveFilterParams());
  const res = await fetch(`/api/anomalies-and-forecast?${params.toString()}`);
  const data = await res.json();

  const fc = data.forecast_6m || [];
  if (fc.length > 0 && window.Plotly) {
    Plotly.newPlot('chart-forecast', [
      {
        x: fc.map(r => r.Month),
        y: fc.map(r => r.Upper_80),
        name: 'Upper 80% CI',
        type: 'scatter',
        mode: 'lines',
        line: { width: 0 },
        showlegend: false
      },
      {
        x: fc.map(r => r.Month),
        y: fc.map(r => r.Lower_80),
        name: '80% Confidence Band',
        type: 'scatter',
        mode: 'lines',
        fill: 'tonexty',
        fillcolor: 'rgba(157, 147, 134, 0.30)',
        line: { width: 0 }
      },
      {
        x: fc.map(r => r.Month),
        y: fc.map(r => r.Forecasted_Orders),
        name: 'Forecasted Dispatches',
        type: 'scatter',
        mode: 'lines+markers',
        line: { color: '#2C343D', width: 2.5 },
        marker: { size: 6, color: '#2C343D' }
      }
    ], {
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, sans-serif', color: THEME.textSub, size: 11 },
      margin: { t: 15, r: 20, b: 36, l: 42 },
      xaxis: { gridcolor: 'rgba(44,52,61,0.1)' },
      yaxis: { gridcolor: 'rgba(44,52,61,0.1)' },
      legend: { orientation: 'h', y: 1.12, x: 0 }
    }, PLOTLY_CONFIG);
  }

  const tbody = document.getElementById('anomaly-table-body');
  tbody.innerHTML = (data.top_anomalies || []).map(a => `
    <tr class="hover:bg-[#EAE5DE]">
      <td class="py-2 px-2.5 font-bold text-[#1F2428]">${a.Order_ID}</td>
      <td class="py-2 px-2.5">${a.City} · <span class="text-[#686E73]">${a.Vendor}</span></td>
      <td class="py-2 px-2.5">${fmtINR(a.Order_Value_INR)}</td>
      <td class="py-2 px-2.5">${a.Delivery_Lead_Time_Days}d / <strong class="text-[#A63A3A]">+${a.Calculated_Delay_Days}d</strong></td>
      <td class="py-2 px-2.5 font-bold">${a.Delivery_Attempts}</td>
      <td class="py-2 px-2.5"><span class="px-2 py-0.5 rounded bg-[#E6E1DA] text-[#1F2428] font-bold">${a.Anomaly_Rank}th</span></td>
    </tr>
  `).join('');
}

window.addEventListener('DOMContentLoaded', initApp);
