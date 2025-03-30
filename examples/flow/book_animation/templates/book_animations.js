// Intersection Observer for chapter animations
const observerOptions = {
    root: null,
    rootMargin: '0px',
    threshold: 0.1
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
        }
    });
}, observerOptions);

// Initialize observers for all chapters
document.querySelectorAll('.chapter-section').forEach(chapter => {
    observer.observe(chapter);
});

// Chapter navigation menu
const menuToggle = document.getElementById('menu-toggle');
const chapterMenu = document.getElementById('chapter-menu');

menuToggle.addEventListener('click', () => {
    chapterMenu.classList.toggle('hidden');
});

// Close menu when clicking outside
document.addEventListener('click', (event) => {
    if (!menuToggle.contains(event.target) && !chapterMenu.contains(event.target)) {
        chapterMenu.classList.add('hidden');
    }
});

// Smooth scrolling for chapter navigation
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        chapterMenu.classList.add('hidden');
        
        const targetId = this.getAttribute('href');
        const targetElement = document.querySelector(targetId);
        
        if (targetElement) {
            targetElement.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Custom transitions
const transitions = {{ transitions | tojson }};

// Apply custom transitions
Object.entries(transitions).forEach(([selector, effect]) => {
    const elements = document.querySelectorAll(selector);
    elements.forEach(element => {
        element.style.transition = effect;
    });
});
