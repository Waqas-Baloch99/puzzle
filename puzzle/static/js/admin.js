// admin.js
document.addEventListener('DOMContentLoaded', () => {
    // Constants
    const NEON_GLOW_DURATION = 200;

    // Utility Functions
    const addGlowEffect = (element) => {
        element.classList.add('neon-glow');
        setTimeout(() => element.classList.remove('neon-glow'), NEON_GLOW_DURATION);
    };

    // Button Interactions
    const newPuzzleBtn = document.querySelector('.btn-outline-neon');
    const filterBtn = document.querySelector('.btn-outline-secondary');

    if (newPuzzleBtn) {
        newPuzzleBtn.addEventListener('click', (e) => {
            e.preventDefault();
            addGlowEffect(newPuzzleBtn);
            // Placeholder for new puzzle creation logic
            console.log('New Puzzle button clicked');
            // Could open a modal or redirect:
            // window.location.href = '/admin/puzzles/new/';
        });
    }

    if (filterBtn) {
        filterBtn.addEventListener('click', (e) => {
            e.preventDefault();
            addGlowEffect(filterBtn);
            toggleFilterPanel();
        });
    }

    // Filter Panel (stub - implement as needed)
    function toggleFilterPanel() {
        const filterPanel = document.querySelector('.filter-panel');
        if (filterPanel) {
            filterPanel.classList.toggle('active');
        } else {
            console.log('Filter panel not implemented yet');
            // Could dynamically create a filter panel here
        }
    }

    // Table Row Interactions
    const tableRows = document.querySelectorAll('.table tbody tr.cursor-pointer');
    tableRows.forEach(row => {
        row.addEventListener('click', () => {
            addGlowEffect(row);
            const username = row.querySelector('td:first-child span').textContent;
            const puzzleTitle = row.querySelector('td:nth-child(2)').textContent;
            console.log(`Clicked submission: ${username} - ${puzzleTitle}`);
            // Could redirect to submission detail:
            // window.location.href = `/admin/submissions/${submissionId}/`;
        });

        row.addEventListener('mouseenter', () => {
            row.style.transition = 'box-shadow 0.2s ease';
            row.style.boxShadow = '0 0 10px var(--ai-shadow)';
        });

        row.addEventListener('mouseleave', () => {
            row.style.boxShadow = 'none';
        });
    });

    // Stat Card Animations
    const statCards = document.querySelectorAll('.stat-card');
    statCards.forEach(card => {
        card.addEventListener('mouseenter', () => {
            card.style.transition = 'transform 0.3s ease, box-shadow 0.3s ease';
            card.querySelector('i').classList.add('animate-pulse');
        });

        card.addEventListener('mouseleave', () => {
            card.querySelector('i').classList.remove('animate-pulse');
        });
    });

    // Category Card Hover Effects
    const categoryCards = document.querySelectorAll('.category-card');
    categoryCards.forEach(card => {
        card.addEventListener('mouseenter', () => {
            const icon = card.querySelector('i');
            icon.style.transition = 'transform 0.3s ease';
            icon.style.transform = 'scale(1.2)';
        });

        card.addEventListener('mouseleave', () => {
            const icon = card.querySelector('i');
            icon.style.transform = 'scale(1)';
        });
    });

    // Smooth Scroll for Long Pages
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', (e) => {
            e.preventDefault();
            const target = document.querySelector(anchor.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });
});

// CSS to be added to admin.css or inline in base_admin.html
const styleSheet = document.createElement('style');
styleSheet.textContent = `
    .neon-glow {
        box-shadow: 0 0 15px var(--ai-neon), 0 0 25px var(--ai-shadow) !important;
        transition: box-shadow 0.2s ease;
    }

    .animate-pulse {
        animation: pulse 1.5s infinite;
    }

    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.1); }
        100% { transform: scale(1); }
    }
`;
document.head.appendChild(styleSheet);