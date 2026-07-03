// web/app.js
var focusedRow = null;
var isPinned = false;
var isPaused = false;
var newItemsCount = 0;

// 1. Controls & Toggles
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('btn-pin').addEventListener('click', (e) => {
        isPinned = !isPinned;
        e.currentTarget.classList.toggle('active-pin', isPinned);
        eel.toggle_topmost(isPinned);
    });

    document.getElementById('btn-pause').addEventListener('click', (e) => {
        isPaused = !isPaused;
        e.currentTarget.innerHTML = isPaused ? '<i class="fa-solid fa-pause"></i>' : '<i class="fa-solid fa-play"></i>';
        e.currentTarget.classList.toggle('active-pause', isPaused);
        eel.toggle_setting('pause', isPaused);
    });

    document.getElementById('toggle-diff').addEventListener('change', (e) => eel.toggle_setting('diff', e.target.checked));
    document.getElementById('toggle-dedent').addEventListener('change', (e) => eel.toggle_setting('dedent', e.target.checked));

    // Search and Filter Listeners
    document.getElementById('search-input').addEventListener('input', applyFilters);
    document.getElementById('date-filter').addEventListener('change', applyFilters);

    // Clear History Listener
    document.getElementById('btn-clear').addEventListener('click', () => {
        if (confirm("Are you sure you want to permanently clear all history?")) {
            eel.clear_history_data()().then(() => {
                document.getElementById('scroll-container').innerHTML = '';
                showToast("History completely cleared.");
            });
        }
    });
});

function applyFilters() {
    const query = document.getElementById('search-input').value.toLowerCase();
    const dateFilter = document.getElementById('date-filter').value;

    document.querySelectorAll('.history-row').forEach(row => {
        const rowText = row.getAttribute('data-text');
        const rowDate = row.getAttribute('data-date');
        const matchesSearch = !query || rowText.includes(query);
        const matchesDate = !dateFilter || rowDate === dateFilter;

        if (matchesSearch && matchesDate) {
            row.classList.remove('hidden');
        } else {
            row.classList.add('hidden');
        }
    });

    document.querySelectorAll('.date-divider').forEach(div => {
        const date = div.getAttribute('data-date');
        const hasVisible = document.querySelector(`.history-row[data-date="${date}"]:not(.hidden)`);
        div.classList.toggle('hidden', !hasVisible);
    });
}

function escapeHTML(str) {
    return str.replace(/[&<>'"]/g, tag => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    }[tag]));
}

function formatText(text) {
    // Strip \r to avoid double newlines in HTML
    return text.replace(/\r\n/g, '\n').split('\n').map(line => {
        const escaped = escapeHTML(line);
        if (line.startsWith('+')) return `<span class="line-plus">${escaped}</span>`;
        if (line.startsWith('-')) return `<span class="line-minus">${escaped}</span>`;
        return `<span class="line-normal">${escaped}</span>`;
    }).join('\n');
}

// 3. UI Generation & Appending
function createRow(originalText, cleanedText, labels, dateStr, isHistorical = false) {
    const row = document.createElement('div');
    row.className = 'history-row';
    row.setAttribute('data-date', dateStr);
    row.setAttribute('data-text', (originalText + " " + cleanedText).toLowerCase());

    const isSame = originalText === cleanedText;

    function buildCol(text, isMerged) {
        const col = document.createElement('div');
        col.className = 'col' + (isMerged ? ' single-col' : '');
        col.innerHTML = formatText(text);

        if (labels && labels.length > 0) {
            const lblContainer = document.createElement('div');
            lblContainer.className = 'labels-container';
            labels.forEach(lbl => {
                const badge = document.createElement('span');
                badge.className = 'label-badge';
                badge.innerText = lbl;
                lblContainer.appendChild(badge);
            });
            col.appendChild(lblContainer);
        }
        attachClickHandlers(col, text);
        return col;
    }

    if (isSame) {
        row.appendChild(buildCol(cleanedText, true));
    } else {
        row.appendChild(buildCol(originalText, false));
        row.appendChild(buildCol(cleanedText, false));
    }

    const container = document.getElementById('scroll-container');
    if (isHistorical) {
        container.appendChild(row);
    } else {
        // Prepend new live items to the top, right under any headers/dividers if needed
        container.insertBefore(row, container.firstChild);
    }
    setTimeout(() => {
        row.querySelectorAll('.col').forEach(col => {
            if (col.scrollHeight > col.clientHeight) {
                const gradient = document.createElement('div');
                gradient.className = 'gradient-overlay';
                gradient.innerText = '▼ Click to expand';
                gradient.addEventListener('click', (e) => {
                    e.stopPropagation();
                    col.classList.add('expanded');
                    gradient.remove();
                });
                col.appendChild(gradient);
            }
        });
    }, 50);
}


// 4. Click handlers (Single copy, double edit)
function attachClickHandlers(element, rawContent) {
    let clickTimer = null;
    let isEditing = false;

    element.addEventListener('click', (e) => {
        if (isEditing) return;

        if (clickTimer === null) {
            clickTimer = setTimeout(() => {
                clickTimer = null;
                // Visual feedback animation
                element.classList.add('clicked-anim');
                setTimeout(() => element.classList.remove('clicked-anim'), 400);

                // Tell Python to ignore NEXT, then copy to clipboard after a tiny delay
                eel.ignore_next_copy(rawContent)();
                setTimeout(() => {
                    navigator.clipboard.writeText(rawContent).then(() => {
                        showToast("Column Copied!");
                    });
                }, 50);
            }, 250); // 250ms delay to wait and see if it's a double click
        } else {
            // Double Click: Edit
            clearTimeout(clickTimer);
            clickTimer = null;
            isEditing = true;

            const grad = element.querySelector('.gradient-overlay');
            if (grad) grad.remove();
            element.classList.add('expanded');

            const textarea = document.createElement('textarea');
            textarea.value = rawContent;
            element.innerHTML = '';
            element.appendChild(textarea);
            textarea.focus();

            textarea.addEventListener('blur', () => {
                element.innerHTML = formatText(textarea.value);
                isEditing = false;
            });
        }
    });
}


// 5. Global Keyboard Shortcuts
document.addEventListener('keydown', (e) => {
    // Ctrl + C to copy the hovered row (replaced focusedRow logic)
    const hoveredRow = document.querySelector('.history-row:hover');
    if (e.ctrlKey && e.key === 'c' && hoveredRow) {
        const cols = hoveredRow.querySelectorAll('.col');
        let textToCopy = "";
        if (cols.length === 1) {
            textToCopy = cols[0].innerText;
        } else if (cols.length === 2) {
            textToCopy = `${cols[0].innerText}\n---\n${cols[1].innerText}`;
        }
        if (textToCopy) {
            navigator.clipboard.writeText(textToCopy).then(() => showToast("Row Copied!"));
        }
    }
});


// 6. Utility & Initialization
function showToast(message) {
    const toast = document.getElementById('toast');
    toast.innerText = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2000);
}

// Receive new entries dynamically from Python
eel.expose(add_new_entry);

function add_new_entry(original, cleaned, labels) {
    const container = document.getElementById('scroll-container');
    const isNearTop = container.scrollTop < 50;

    // Generate current local date in YYYY-MM-DD format
    const now = new Date();
    const offset = now.getTimezoneOffset() * 60000;
    const todayStr = (new Date(now - offset)).toISOString().split('T')[0];

    createRow(original, cleaned, labels, todayStr, false);

    if (!isNearTop) {
        newItemsCount++;
        const btn = document.getElementById('new-items-btn');
        btn.innerHTML = `<i class="fa-solid fa-arrow-up"></i> ${newItemsCount} New Item${newItemsCount > 1 ? 's' : ''}`;
        btn.classList.add('show');
    } else {
        container.scrollTo({top: 0, behavior: 'smooth'});
    }
}

document.getElementById('new-items-btn').addEventListener('click', () => {
    document.getElementById('scroll-container').scrollTo({top: 0, behavior: 'smooth'});
    newItemsCount = 0;
    document.getElementById('new-items-btn').classList.remove('show');
});

document.getElementById('scroll-container').addEventListener('scroll', (e) => {
    if (e.target.scrollTop < 50 && newItemsCount > 0) {
        newItemsCount = 0;
        document.getElementById('new-items-btn').classList.remove('show');
    }
});

eel.expose(close_window);

function close_window() {
    window.close();
}

// --- Update window.onload ---
window.addEventListener('load', async () => {
    const historyData = await eel.get_history()();
    const container = document.getElementById('scroll-container');

    // Sort dates descending
    const dates = Object.keys(historyData).sort((a, b) => b.localeCompare(a));

    for (const dateStr of dates) {
        const divider = document.createElement('div');
        divider.className = 'date-divider';
        divider.setAttribute('data-date', dateStr);
        divider.innerText = dateStr;
        container.appendChild(divider);

        // Reverse entries to show newest first
        const entries = historyData[dateStr].slice().reverse();
        entries.forEach(entry => {
            createRow(entry.original, entry.cleaned, entry.labels, dateStr, true);
        });
    }
    eel.set_gui_ready()();
});