// ── PickleTurf dashboard charts ────────────────────────────────────────────────
// Theme-aware: colors are read from CSS custom properties and charts are
// rebuilt when the theme toggles (main.js dispatches `pt:themechange`).

Chart.defaults.font.family = "'Outfit', system-ui, sans-serif";
Chart.defaults.font.size   = 12;

const chartInstances = [];

let dailyRange = 30;
let dailyChart = null;

function cssVar(name) {
    return getComputedStyle(document.documentElement)
        .getPropertyValue(name)
        .trim();
}

function palette() {
    return {
        tick:     cssVar('--chart-tick'),
        grid:     cssVar('--chart-grid'),
        primary:  cssVar('--chart-primary'),
        accent:   cssVar('--chart-accent'),
        fill:     cssVar('--chart-fill'),
        cardBg:   cssVar('--bg-card'),
        ok:       cssVar('--ok'),
        info:     cssVar('--info'),
    };
}

function pesoTooltip() {
    return {
        callbacks: {
            label: ctx => {
                const v = ctx.parsed.y !== undefined ? ctx.parsed.y : ctx.parsed;
                return ` ₱${Number(v).toLocaleString()}`;
            }
        }
    };
}

function buildCharts() {
    while (chartInstances.length) chartInstances.pop().destroy();

    const p = palette();
    Chart.defaults.color = p.tick;

    // ── 1. Daily Revenue (line) ───────────────────────────────────────────────
    const dailyEl = document.getElementById('dailyRevenueChart');
    if (dailyEl) {
        dailyChart = new Chart(dailyEl, {
            type: 'line',
            data: {
                labels: dailyLabels.slice(-dailyRange),
                datasets: [{
                    label: 'Revenue (₱)',
                    data: dailyData.slice(-dailyRange),
                    borderColor: p.primary,
                    backgroundColor: p.fill,
                    borderWidth: 2,
                    pointRadius: 2,
                    pointHoverRadius: 5,
                    fill: true,
                    tension: 0.3,
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false },
                    tooltip: pesoTooltip(),
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { maxTicksLimit: 10, maxRotation: 0 }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: p.grid },
                        ticks: { callback: v => '₱' + v.toLocaleString() }
                    }
                }
            }
        });
        chartInstances.push(dailyChart);
    } else {
        dailyChart = null;
    }

    // ── 2. Revenue by Type (doughnut) ─────────────────────────────────────────
    const typeEl = document.getElementById('revenueTypeChart');
    if (typeEl && typeof typeData !== 'undefined' && typeData.length > 0) {
        const typeColors = {
            'Court Booking':      p.ok,
            'Equipment Rental':   p.accent,
            'Item Sale':          p.info,
            'Open Play':          '#0dcaf0',
            'Manual Entry':       '#8B5CF6',
        };
        chartInstances.push(new Chart(typeEl, {
            type: 'doughnut',
            data: {
                labels: typeLabels,
                datasets: [{
                    data: typeData,
                    backgroundColor: typeLabels.map(
                        label => typeColors[label] || '#94A3B8'
                    ),
                    borderWidth: 2,
                    borderColor: p.cardBg,
                }]
            },
            options: {
                responsive: true,
                cutout: '65%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { padding: 12, boxWidth: 12 }
                    },
                    tooltip: pesoTooltip(),
                }
            }
        }));
    }

    // ── 3. Monthly Revenue (bar) ──────────────────────────────────────────────
    const monthlyEl = document.getElementById('monthlyRevenueChart');
    if (monthlyEl) {
        chartInstances.push(new Chart(monthlyEl, {
            type: 'bar',
            data: {
                labels: monthlyLabels,
                datasets: [{
                    label: 'Revenue (₱)',
                    data: monthlyData,
                    backgroundColor: p.accent,
                    hoverBackgroundColor: cssVar('--pt-yellow-dark'),
                    borderRadius: 4,
                    borderSkipped: false,
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false },
                    tooltip: pesoTooltip(),
                },
                scales: {
                    x: { grid: { display: false } },
                    y: {
                        beginAtZero: true,
                        grid: { color: p.grid },
                        ticks: { callback: v => '₱' + v.toLocaleString() }
                    }
                }
            }
        }));
    }
}

document.addEventListener('pt:themechange', buildCharts);
buildCharts();

// ── Daily revenue range toggle (7 / 14 / 30 days) ─────────────────────────────
document.querySelectorAll('.btn-range [data-range]').forEach(btn => {
    btn.addEventListener('click', () => {
        dailyRange = Number(btn.dataset.range) || 30;
        document.querySelectorAll('.btn-range [data-range]')
            .forEach(b => b.classList.toggle('active', b === btn));

        if (dailyChart) {
            dailyChart.data.labels = dailyLabels.slice(-dailyRange);
            dailyChart.data.datasets[0].data = dailyData.slice(-dailyRange);
            dailyChart.update();
        }
    });
});
