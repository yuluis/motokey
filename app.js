// === Cart State ===
let cart = [];

const products = {
    basic: { name: 'MotoKey Basic', price: 89 },
    enhanced: { name: 'MotoKey Enhanced', price: 149 }
};

// === Cart Functions ===
function addToCart(productId) {
    const product = products[productId];
    cart.push({ id: productId, ...product });
    updateCartUI();
    showCartButton();

    // Brief visual feedback
    const btn = event.target;
    const original = btn.textContent;
    btn.textContent = 'Added!';
    btn.style.background = '#44ff44';
    btn.style.color = '#0d1117';
    setTimeout(() => {
        btn.textContent = original;
        btn.style.background = '';
        btn.style.color = '';
    }, 800);
}

function removeFromCart(index) {
    cart.splice(index, 1);
    updateCartUI();
    if (cart.length === 0) {
        document.getElementById('cart-btn').style.display = 'none';
        closeCart();
    }
}

function updateCartUI() {
    const countEl = document.getElementById('cart-count');
    const itemsEl = document.getElementById('cart-items');
    const totalEl = document.getElementById('cart-total');

    countEl.textContent = cart.length;

    if (cart.length === 0) {
        itemsEl.innerHTML = '<p style="color: var(--text-muted); padding: 20px 0;">Your cart is empty.</p>';
        totalEl.textContent = '';
        return;
    }

    itemsEl.innerHTML = cart.map((item, i) => `
        <div class="cart-item">
            <span class="cart-item-name">${item.name}</span>
            <span>
                <span class="cart-item-price">$${item.price}</span>
                <span class="cart-item-remove" onclick="removeFromCart(${i})">remove</span>
            </span>
        </div>
    `).join('');

    const total = cart.reduce((sum, item) => sum + item.price, 0);
    totalEl.textContent = `Total: $${total}`;
}

function showCartButton() {
    document.getElementById('cart-btn').style.display = 'block';
}

function openCart() {
    updateCartUI();
    document.getElementById('cart-modal').style.display = 'flex';
}

function closeCart() {
    document.getElementById('cart-modal').style.display = 'none';
}

// === FAQ Toggle ===
function toggleFaq(el) {
    const answer = el.nextElementSibling;
    const isOpen = el.classList.contains('active');

    // Close all
    document.querySelectorAll('.faq-question').forEach(q => {
        q.classList.remove('active');
        q.nextElementSibling.style.maxHeight = '0';
    });

    // Open clicked (if was closed)
    if (!isOpen) {
        el.classList.add('active');
        answer.style.maxHeight = answer.scrollHeight + 'px';
    }
}

// === Close modal on outside click ===
document.getElementById('cart-modal').addEventListener('click', function(e) {
    if (e.target === this) closeCart();
});

// === Smooth scroll for nav links ===
document.querySelectorAll('.nav-links a').forEach(link => {
    link.addEventListener('click', function(e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
});
