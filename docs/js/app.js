// MEP Voting Analysis - Frontend
// Data is loaded from data/mep_data.json

const PARTY_COLORS = {
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

let allData = [];
let currentTopic = 'all';

async function loadData() {
    try {
        const response = await fetch('data/mep_data.json');
        allData = await response.json();
        initializeTopics();
        renderChart();
        renderStats();
    } catch (error) {
        document.getElementById('scatter-plot').innerHTML =
            `<div class="loading">Error loading data: ${error.message}<br>
             Run <code>python export_json.py</code> to generate the data file.</div>`;
    }
}

function initializeTopics() {
    // Extract unique topics from data
    const topics = new Set();
    allData.forEach(d => {
        if (d.topics) {
            d.topics.split(', ').forEach(t => topics.add(t.trim()));
        }
    });

    const container = document.getElementById('topic-filters');
    const sortedTopics = Array.from(topics).sort();

    sortedTopics.forEach(topic => {
        const btn = document.createElement('button');
        btn.className = 'topic-btn';
        btn.dataset.topic = topic;
        btn.textContent = topic;
        btn.onclick = () => filterByTopic(topic);
        container.appendChild(btn);
    });

    // Add click handler to "All" button
    document.querySelector('[data-topic="all"]').onclick = () => filterByTopic('all');
}

function filterByTopic(topic) {
    currentTopic = topic;

    // Update button states
    document.querySelectorAll('.topic-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.topic === topic);
    });

    renderChart();
    renderStats();
}

function getFilteredData() {
    if (currentTopic === 'all') return allData;
    return allData.filter(d => d.topics && d.topics.toLowerCase().includes(currentTopic.toLowerCase()));
}

function renderChart() {
    const data = getFilteredData();

    // Group by party
    const parties = [...new Set(data.map(d => d.party))].sort();

    const traces = parties.map(party => {
        const partyData = data.filter(d => d.party === party);
        return {
            name: party,
            x: partyData.map(() => party),
            y: partyData.map(d => d.avg_rebel_score),
            text: partyData.map(d => `${d.first_name} ${d.last_name}<br>Country: ${d.country}<br>Votes: ${d.n_votes}<br>Rebel Score: ${d.avg_rebel_score.toFixed(4)}`),
            mode: 'markers',
            type: 'scatter',
            marker: {
                color: PARTY_COLORS[party] || '#666',
                size: 8,
                opacity: 0.7,
            },
            hoverinfo: 'text',
        };
    });

    const layout = {
        title: currentTopic === 'all' ? 'MEP Rebel Scores by Party' : `MEP Rebel Scores - ${currentTopic}`,
        xaxis: {
            title: 'Party',
            categoryorder: 'array',
            categoryarray: parties,
        },
        yaxis: {
            title: 'Average Rebel Score',
            zeroline: true,
        },
        hovermode: 'closest',
        showlegend: true,
        legend: {
            orientation: 'h',
            y: -0.15,
        },
        margin: { t: 50, b: 100 },
    };

    const config = {
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ['lasso2d', 'select2d'],
    };

    Plotly.newPlot('scatter-plot', traces, layout, config);
}

function renderStats() {
    const data = getFilteredData();

    const totalMEPs = data.length;
    const avgRebel = data.reduce((sum, d) => sum + d.avg_rebel_score, 0) / data.length;
    const outliers = data.filter(d => d.is_outlier).length;
    const parties = new Set(data.map(d => d.party)).size;

    const statsHtml = `
        <div class="stat-card">
            <h3>Total MEPs</h3>
            <div class="value">${totalMEPs.toLocaleString()}</div>
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
            <h3>Parties</h3>
            <div class="value">${parties}</div>
        </div>
    `;

    document.getElementById('stats').innerHTML = statsHtml;
}

// Initialize
loadData();
