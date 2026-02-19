/**
 * Trace Viewer - Interactive Pipeline Visualization
 *
 * A lightweight JSON diff library is bundled inline.
 */

(function() {
    'use strict';

    // ============== State ==============
    let sessions = [];
    let selectedSession = null;
    let selectedNodeIndex = null;
    let selectedArrowIndex = null;
    let compareMode = false;
    let compareSession = null;
    let showIgnored = true;

    // ============== DOM Elements ==============
    const sessionsList = document.getElementById('sessions-list');
    const sessionSearch = document.getElementById('session-search');
    const timeline = document.getElementById('timeline');
    const detailPanel = document.getElementById('detail-panel');
    const refreshBtn = document.getElementById('refresh-btn');
    const compareBtn = document.getElementById('compare-btn');
    const exportDiffBtn = document.getElementById('export-diff');
    const showIgnoredToggle = document.getElementById('show-ignored');

    // ============== Initialization ==============
    async function init() {
        await loadSessions();
        setupEventListeners();
    }

    function setupEventListeners() {
        // Refresh button
        refreshBtn.addEventListener('click', loadSessions);

        // Search
        sessionSearch.addEventListener('input', filterSessions);

        // Compare button
        compareBtn.addEventListener('click', toggleCompareMode);

        // Export button
        exportDiffBtn.addEventListener('click', exportDiffAsMarkdown);

        // Show ignored toggle
        showIgnoredToggle.addEventListener('change', (e) => {
            showIgnored = e.target.checked;
            if (selectedSession) {
                renderTimeline(selectedSession);
            }
        });
    }

    // ============== API Calls ==============
    async function loadSessions() {
        try {
            const response = await fetch('/api/sessions');
            sessions = await response.json();
            renderSessionsList(sessions);
        } catch (error) {
            console.error('Failed to load sessions:', error);
            sessionsList.innerHTML = '<div class="loading">Failed to load sessions</div>';
        }
    }

    async function loadSession(sessionName) {
        try {
            const response = await fetch(`/api/session/${sessionName}`);
            return await response.json();
        } catch (error) {
            console.error('Failed to load session:', error);
            return null;
        }
    }

    async function loadDiff(sessionA, sessionB) {
        try {
            const response = await fetch(`/api/diff/${sessionA}/${sessionB}`);
            return await response.json();
        } catch (error) {
            console.error('Failed to load diff:', error);
            return null;
        }
    }

    // ============== Rendering ==============
    function renderSessionsList(sessionsToRender) {
        if (sessionsToRender.length === 0) {
            sessionsList.innerHTML = '<div class="loading">No sessions found</div>';
            return;
        }

        sessionsList.innerHTML = sessionsToRender.map(session => `
            <div class="session-item ${selectedSession === session.name ? 'selected' : ''}"
                 data-session="${session.name}">
                <div class="session-name">${escapeHtml(session.name)}</div>
                <div class="session-meta">
                    <span>${session.hop_count} hops</span>
                    <span class="health-badge ${session.health}">${session.health}</span>
                </div>
            </div>
        `).join('');

        // Add click handlers
        sessionsList.querySelectorAll('.session-item').forEach(item => {
            item.addEventListener('click', () => selectSession(item.dataset.session));
        });
    }

    function filterSessions() {
        const query = sessionSearch.value.toLowerCase();
        const filtered = sessions.filter(s => s.name.toLowerCase().includes(query));
        renderSessionsList(filtered);
    }

    async function selectSession(sessionName) {
        selectedSession = sessionName;
        selectedNodeIndex = null;
        selectedArrowIndex = null;

        // Update UI
        renderSessionsList(sessions);
        compareBtn.disabled = !compareMode;

        // Load session data
        const session = await loadSession(sessionName);
        if (session) {
            renderTimeline(session);
            renderDetailPanel(null);
        }
    }

    function renderTimeline(session) {
        const hops = session.hops || [];

        if (hops.length === 0) {
            timeline.innerHTML = `
                <div class="empty-state">
                    <p>No pipeline data for this session</p>
                </div>
            `;
            return;
        }

        let html = '<div class="timeline-nodes">';

        hops.forEach((hop, index) => {
            const status = hop.success ? 'success' : 'error';
            const statusLabel = hop.success ? '✓' : '✗';
            const stageName = hop.stage || `Hop ${hop.hop_number || index + 1}`;

            // Determine node color based on diff status (if in compare mode)
            let colorClass = '';
            if (compareSession && index < hops.length - 1) {
                // Check diff between this hop and next
                // For now, we'll default to green
                colorClass = 'green';
            }

            html += `
                <div class="pipeline-node ${colorClass} ${selectedNodeIndex === index ? 'selected' : ''}"
                     data-index="${index}">
                    <span class="node-label">${escapeHtml(stageName)}</span>
                    <span class="node-status ${status}">${statusLabel}</span>
                </div>
            `;

            // Add arrow between nodes (except for last)
            if (index < hops.length - 1) {
                let arrowClass = '';
                if (compareSession) {
                    arrowClass = 'has-diff'; // Could be more sophisticated
                }
                html += `
                    <div class="node-arrow ${arrowClass} ${selectedArrowIndex === index ? 'selected' : ''}"
                         data-index="${index}"></div>
                `;
            }
        });

        html += '</div>';
        timeline.innerHTML = html;

        // Add click handlers
        timeline.querySelectorAll('.pipeline-node').forEach(node => {
            node.addEventListener('click', () => {
                selectedNodeIndex = parseInt(node.dataset.index);
                selectedArrowIndex = null;
                renderTimeline(session);
                showNodeDetails(session, selectedNodeIndex);
            });
        });

        timeline.querySelectorAll('.node-arrow').forEach(arrow => {
            arrow.addEventListener('click', () => {
                selectedArrowIndex = parseInt(arrow.dataset.index);
                selectedNodeIndex = null;
                renderTimeline(session);
                showArrowDetails(session, selectedArrowIndex);
            });
        });
    }

    function showNodeDetails(session, nodeIndex) {
        const hops = session.hops || [];
        const hop = hops[nodeIndex];

        if (!hop) return;

        const beforeJson = JSON.stringify(hop.before || {}, null, 2);
        const afterJson = JSON.stringify(hop.after || {}, null, 2);

        const stageName = hop.stage || `Hop ${hop.hop_number || nodeIndex + 1}`;

        detailPanel.innerHTML = `
            <div class="detail-content">
                <div class="detail-json">
                    <div class="json-header">Input (Before ${stageName})</div>
                    <pre>${escapeHtml(beforeJson)}</pre>
                </div>
                <div class="detail-json">
                    <div class="json-header">Output (After ${stageName})</div>
                    <pre>${escapeHtml(afterJson)}</pre>
                </div>
            </div>
        `;
    }

    async function showArrowDetails(session, arrowIndex) {
        const hops = session.hops || [];

        if (arrowIndex >= hops.length - 1) return;

        const fromHop = hops[arrowIndex];
        const toHop = hops[arrowIndex + 1];
        const sessionA = selectedSession;

        // For now, we compare consecutive hops within the same session
        // Or we could compare with another session in compare mode
        let diffData;

        if (compareSession) {
            // Compare hops across sessions
            diffData = await loadDiff(selectedSession, compareSession);
        } else {
            // Compute diff between consecutive hops within session
            diffData = await loadDiff(`${selectedSession}-hop-${arrowIndex}`, `${selectedSession}-hop-${arrowIndex + 1}`);
            // This won't work since we don't have individual hop sessions
            // Instead, compute inline diff
            diffData = computeInlineDiff(fromHop.after || {}, toHop.before || {});
        }

        renderDiffDetails(diffData);
    }

    function computeInlineDiff(dataA, dataB) {
        const differences = [];
        diffRecursive(dataA, dataB, '', differences);

        return {
            identical: differences.length === 0,
            differences: differences.map(d => ({
                path: d.path,
                type: d.type,
                value_a: d.valueA,
                value_b: d.valueB
            }))
        };
    }

    function diffRecursive(a, b, path, differences) {
        // Handle null/undefined
        if (a === null && b === null) return;
        if (a === null || b === null) {
            differences.push({ path, type: 'changed', valueA: a, valueB: b });
            return;
        }

        // Type mismatch
        if (typeof a !== typeof b) {
            differences.push({ path, type: 'changed', valueA: a, valueB: b });
            return;
        }

        // Handle objects
        if (typeof a === 'object' && !Array.isArray(a)) {
            const allKeys = new Set([...Object.keys(a || {}), ...Object.keys(b || {})]);
            for (const key of allKeys) {
                const newPath = path ? `${path}.${key}` : key;
                if (!(key in a)) {
                    differences.push({ path: newPath, type: 'added', valueA: null, valueB: b[key] });
                } else if (!(key in b)) {
                    differences.push({ path: newPath, type: 'removed', valueA: a[key], valueB: null });
                } else {
                    diffRecursive(a[key], b[key], newPath, differences);
                }
            }
            return;
        }

        // Handle arrays
        if (Array.isArray(a)) {
            if (a.length !== b.length) {
                differences.push({ path, type: 'changed', valueA: a, valueB: b });
            } else {
                for (let i = 0; i < a.length; i++) {
                    diffRecursive(a[i], b[i], `${path}[${i}]`, differences);
                }
            }
            return;
        }

        // Simple values
        if (a !== b) {
            differences.push({ path, type: 'changed', valueA: a, valueB: b });
        }
    }

    async function renderDiffDetails(diffData) {
        if (!diffData) {
            detailPanel.innerHTML = '<div class="empty-state"><p>No diff data available</p></div>';
            return;
        }

        if (diffData.identical) {
            detailPanel.innerHTML = `
                <div class="empty-state">
                    <p style="color: var(--accent-green)">✓ No differences - payloads are identical</p>
                </div>
            `;
            return;
        }

        const diffItemsHtml = diffData.differences.map(diff => `
            <div class="diff-item ${diff.type}">
                <div class="diff-path">${escapeHtml(diff.path)}</div>
                <div class="diff-values">
                    ${diff.value_a !== undefined ? `<div class="diff-value a">${escapeHtml(String(diff.value_a))}</div>` : ''}
                    ${diff.value_b !== undefined ? `<div class="diff-value b">${escapeHtml(String(diff.value_b))}</div>` : ''}
                </div>
            </div>
        `).join('');

        detailPanel.innerHTML = `
            <div class="diff-list">
                <div class="json-header" style="padding: 12px; background: var(--bg-tertiary); margin-bottom: 12px; border-radius: 6px;">
                    Differences: ${diffData.session_a || 'session A'} → ${diffData.session_b || 'session B'}
                </div>
                ${diffItemsHtml}
            </div>
        `;

        exportDiffBtn.disabled = false;
    }

    function renderDetailPanel(content) {
        if (!content) {
            detailPanel.innerHTML = '<div class="empty-state"><p>Click on a node or arrow to see details</p></div>';
            exportDiffBtn.disabled = true;
            return;
        }
        detailPanel.innerHTML = content;
    }

    // ============== Compare Mode ==============
    function toggleCompareMode() {
        compareMode = !compareMode;

        if (!compareMode) {
            compareSession = null;
            compareBtn.textContent = 'Compare Selected';
            compareBtn.classList.remove('btn-primary');
            compareBtn.classList.add('btn-secondary');
        } else {
            compareBtn.textContent = 'Select Second Session';
            compareBtn.classList.remove('btn-secondary');
            compareBtn.classList.add('btn-primary');
        }

        compareBtn.disabled = !compareMode;

        // If now in compare mode and we have a session selected, prompt for second
        if (compareMode && selectedSession) {
            // Add visual indicator to sessions list
            sessionsList.classList.add('compare-mode');
        } else {
            sessionsList.classList.remove('compare-mode');
        }

        // Re-render timeline if session is selected
        if (selectedSession) {
            loadSession(selectedSession).then(session => {
                if (session) renderTimeline(session);
            });
        }
    }

    // ============== Export ==============
    function exportDiffAsMarkdown() {
        if (!selectedSession || !compareSession) return;

        // Generate markdown
        let markdown = `# Diff: ${selectedSession} vs ${compareSession}\n\n`;
        markdown += `Generated by Trace Viewer\n\n`;

        const diffElements = detailPanel.querySelectorAll('.diff-item');
        if (diffElements.length === 0) {
            markdown += 'No differences found.\n';
        } else {
            diffElements.forEach(item => {
                const path = item.querySelector('.diff-path').textContent;
                const values = item.querySelectorAll('.diff-value');

                markdown += `## ${path}\n\n`;

                if (values[0]) {
                    markdown += `- **From**: \`${values[0].textContent}\`\n`;
                }
                if (values[1]) {
                    markdown += `+ **To**: \`${values[1].textContent}\`\n`;
                }
                markdown += '\n';
            });
        }

        // Download as file
        const blob = new Blob([markdown], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `diff-${selectedSession}-${compareSession}.md`;
        a.click();
        URL.revokeObjectURL(url);
    }

    // ============== Utilities ==============
    function escapeHtml(text) {
        if (text === null || text === undefined) return '';
        const div = document.createElement('div');
        div.textContent = String(text);
        return div.innerHTML;
    }

    // ============== Start ==============
    init();
})();
