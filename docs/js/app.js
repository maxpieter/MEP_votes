// MEP Voting Analysis - Frontend
// Data is loaded from data/periods/<period>/mep_data.json or data/periods/<period>/topics/<slug>.json

const GROUP_COLORS = {
    'EPP': '#3399FF',
    'SD': '#FF0000',
    'RENEW': '#FFD700',
    'GREEN_EFA': '#00AA00',
    'ECR': '#0054A5',
    'ID': '#2B3856',
    'GUE_NGL': '#8B0000',
    'NI': '#999999',
    'PFE': '#704214',
    'ESN': '#8B4513',
};

const GROUP_NAMES = {
    'EPP': 'European People\'s Party',
    'SD': 'Socialists & Democrats',
    'RENEW': 'Renew Europe',
    'GREEN_EFA': 'Greens/EFA',
    'ECR': 'European Conservatives',
    'ID': 'Identity and Democracy',
    'GUE_NGL': 'The Left',
    'NI': 'Non-Inscrits',
    'PFE': 'Patriots for Europe',
    'ESN': 'Europe of Sovereign Nations',
};

// Left to right ideological order
const GROUP_ORDER = [
    'GUE_NGL',    // Far Left
    'GREEN_EFA',  // Left / Green
    'SD',         // Center-Left
    'RENEW',      // Center / Liberal
    'EPP',        // Center-Right
    'ECR',        // Right
    'ID',         // Far Right (EP9)
    'PFE',        // Far Right (EP10)
    'ESN',        // Far Right (EP10)
    'NI',         // Non-attached
];

let currentData = [];
let currentMeta = {};  // Contains total_votes, total_meps
let config = {};  // Contains topics, periods, default_period
let currentTopic = 'all';
let currentPeriod = null;

async function loadData() {
    try {
        // Load config (topics, periods)
        const configResponse = await fetch('data/config.json');
        config = await configResponse.json();
        currentPeriod = config.default_period;

        initializePeriods();
        initializeTopics();

        // Load initial data for default period
        await loadPeriodData();
    } catch (error) {
        document.getElementById('scatter-plot').innerHTML =
            `<div class="loading">Error loading data: ${error.message}<br>
             Run <code>python export_all_topics.py</code> to generate the data files.</div>`;
    }
}

function initializePeriods() {
    const container = document.getElementById('period-filters');
    if (!container) return;

    config.periods.forEach(period => {
        const btn = document.createElement('button');
        btn.className = 'filter-option' + (period.id === currentPeriod ? ' active' : '');
        btn.dataset.period = period.id;
        btn.textContent = period.label;
        btn.onclick = () => filterByPeriod(period.id);
        container.appendChild(btn);
    });
}

// Fuzzy search function - returns score (lower is better match, -1 is no match)
function fuzzyMatch(pattern, str) {
    pattern = pattern.toLowerCase();
    str = str.toLowerCase();

    // Exact substring match gets best score
    if (str.includes(pattern)) {
        return str.indexOf(pattern);
    }

    // Fuzzy match - all characters must appear in order
    let patternIdx = 0;
    let score = 0;
    let lastMatchIdx = -1;

    for (let i = 0; i < str.length && patternIdx < pattern.length; i++) {
        if (str[i] === pattern[patternIdx]) {
            // Penalize gaps between matches
            if (lastMatchIdx !== -1) {
                score += (i - lastMatchIdx - 1) * 10;
            }
            lastMatchIdx = i;
            patternIdx++;
        }
    }

    // All pattern characters must be found
    if (patternIdx === pattern.length) {
        return score + 100; // Add base score to rank below exact matches
    }

    return -1; // No match
}

function initializeTopics() {
    const container = document.getElementById('topic-filters');
    const searchInput = document.getElementById('topic-search');
    const sortedTopics = Object.keys(config.topics).sort();

    sortedTopics.forEach(topic => {
        const btn = document.createElement('button');
        btn.className = 'topic-option';
        btn.dataset.topic = topic;
        btn.textContent = topic;
        btn.onclick = () => filterByTopic(topic);
        container.appendChild(btn);
    });

    // Add click handler to "All" button
    document.querySelector('[data-topic="all"]').onclick = () => filterByTopic('all');

    // Add search functionality
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.trim();
            filterTopicList(query);
        });
    }
}

function filterTopicList(query) {
    const buttons = document.querySelectorAll('#topic-filters .topic-option');

    if (!query) {
        // Show all buttons in original order
        buttons.forEach(btn => {
            btn.style.display = '';
            btn.style.order = '';
        });
        return;
    }

    // Score and filter buttons
    const scored = [];
    buttons.forEach(btn => {
        const topic = btn.dataset.topic;
        if (topic === 'all') {
            btn.style.display = '';
            btn.style.order = '-1';
            return;
        }

        const score = fuzzyMatch(query, topic);
        if (score >= 0) {
            btn.style.display = '';
            btn.style.order = score;
            scored.push({ btn, score });
        } else {
            btn.style.display = 'none';
        }
    });
}

async function filterByPeriod(periodId) {
    currentPeriod = periodId;

    // Update button states
    document.querySelectorAll('#period-filters .filter-option').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.period === periodId);
    });

    await loadPeriodData();
}

async function filterByTopic(topic) {
    currentTopic = topic;

    // Update button states
    document.querySelectorAll('.topic-option').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.topic === topic);
    });

    await loadPeriodData();
}

async function loadPeriodData() {
    // Show loading state
    document.getElementById('scatter-plot').innerHTML = '<div class="loading">Loading...</div>';

    try {
        // Build URL based on period and topic
        let url;
        if (currentTopic === 'all') {
            url = `data/periods/${currentPeriod}/mep_data.json`;
        } else {
            const slug = config.topics[currentTopic];
            url = `data/periods/${currentPeriod}/topics/${slug}.json`;
        }

        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`No data available for this combination`);
        }
        const json = await response.json();
        currentData = json.meps;
        currentMeta = json.meta;

        renderChart();
        renderStats();
    } catch (error) {
        document.getElementById('scatter-plot').innerHTML =
            `<div class="loading">No data available for ${currentTopic} in this period.</div>`;
        document.getElementById('stats').innerHTML = '';
    }
}

function getFilteredData() {
    return currentData;
}

// Add jitter to avoid overlapping points
function jitter(value, amount = 0.3) {
    return value + (Math.random() - 0.5) * amount;
}

function renderChart() {
    const data = getFilteredData();

    // Group by political group, sorted by ideology (left to right)
    const groups = [...new Set(data.map(d => d.group))].sort((a, b) => {
        const aIdx = GROUP_ORDER.indexOf(a);
        const bIdx = GROUP_ORDER.indexOf(b);
        // Put unknown groups at the end
        if (aIdx === -1) return 1;
        if (bIdx === -1) return -1;
        return aIdx - bIdx;
    });

    // Create numeric x positions for each group
    const groupToX = Object.fromEntries(groups.map((g, i) => [g, i]));

    const traces = groups.map(group => {
        const groupData = data.filter(d => d.group === group);
        const baseX = groupToX[group];
        return {
            name: group,
            x: groupData.map(() => jitter(baseX)),
            y: groupData.map(d => d.avg_rebel_score),
            customdata: groupData.map(d => d['member.id']),
            text: groupData.map(d =>
                `<b>${d.first_name} ${d.last_name}</b><br>` +
                `Country: ${d.country}<br>` +
                `Votes: ${d.n_votes}<br>` +
                `Rebel Score: ${d.avg_rebel_score.toFixed(4)}<br>` +
                `Z-Score: ${d.z_score.toFixed(2)}<br>` +
                `<i>Click for profile</i>`
            ),
            mode: 'markers',
            type: 'scatter',
            marker: {
                color: GROUP_COLORS[group] || '#64748b',
                size: 9,
                opacity: 0.75,
                line: {
                    color: 'white',
                    width: 1,
                },
            },
            hoverinfo: 'text',
            hoverlabel: {
                bgcolor: 'white',
                bordercolor: GROUP_COLORS[group] || '#64748b',
                font: {
                    family: 'ui-sans-serif, system-ui, sans-serif',
                    size: 13,
                    color: '#1e293b',
                },
            },
        };
    });

    // Get period label for title
    const periodLabel = config.periods.find(p => p.id === currentPeriod)?.label || currentPeriod;
    let title = `MEP Rebel Scores by Group - ${periodLabel}`;
    if (currentTopic !== 'all') {
        title = `MEP Rebel Scores - ${currentTopic} (${periodLabel})`;
    }

    const layout = {
        title: {
            text: title,
            font: {
                family: 'ui-sans-serif, system-ui, sans-serif',
                size: 18,
                color: '#1e293b',
                weight: 600,
            },
        },
        xaxis: {
            title: {
                text: 'Group',
                font: { family: 'ui-sans-serif, system-ui, sans-serif', size: 13, color: '#64748b' },
            },
            tickmode: 'array',
            tickvals: groups.map((_, i) => i),
            ticktext: groups.map(g => GROUP_NAMES[g] || g),
            tickfont: { family: 'ui-sans-serif, system-ui, sans-serif', size: 11, color: '#475569' },
            tickangle: -30,
            gridcolor: '#f1f5f9',
            linecolor: '#e2e8f0',
        },
        yaxis: {
            title: {
                text: 'Average Rebel Score',
                font: { family: 'ui-sans-serif, system-ui, sans-serif', size: 13, color: '#64748b' },
            },
            tickfont: { family: 'ui-sans-serif, system-ui, sans-serif', size: 12, color: '#475569' },
            gridcolor: '#f1f5f9',
            linecolor: '#e2e8f0',
            zeroline: true,
            zerolinecolor: '#e2e8f0',
        },
        hovermode: 'closest',
        showlegend: false,
        margin: { t: 60, b: 120, l: 60, r: 20 },
        paper_bgcolor: 'white',
        plot_bgcolor: 'white',
    };

    const config_plot = {
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ['lasso2d', 'select2d'],
        displaylogo: false,
    };

    Plotly.newPlot('scatter-plot', traces, layout, config_plot);

    // Click handler - open MEP profile
    document.getElementById('scatter-plot').on('plotly_click', function(data) {
        const memberId = data.points[0].customdata;
        window.open(`https://parl8.eu/app/meps/${memberId}`, '_blank');
    });
}

function renderStats() {
    const data = getFilteredData();

    const totalMEPs = data.length;
    const totalVotes = currentMeta.total_votes || 0;
    const avgRebel = data.reduce((sum, d) => sum + d.avg_rebel_score, 0) / data.length;
    const outliers = data.filter(d => d.is_outlier).length;
    const groups = new Set(data.map(d => d.group)).size;

    const statsHtml = `
        <div class="stat-card">
            <h3>MEPs</h3>
            <div class="value">${totalMEPs.toLocaleString()}</div>
        </div>
        <div class="stat-card">
            <h3>Total Votes</h3>
            <div class="value">${totalVotes.toLocaleString()}</div>
        </div>
        <div class="stat-card">
            <h3>Avg Rebel Score</h3>
            <div class="value">${avgRebel.toFixed(4)}</div>
        </div>
        <div class="stat-card">
            <h3>Outliers (z > 2)</h3>
            <div class="value">${outliers}</div>
        </div>
        <div class="stat-card">
            <h3>Groups</h3>
            <div class="value">${groups}</div>
        </div>
    `;

    document.getElementById('stats').innerHTML = statsHtml;
}

// Initialize
loadData();
