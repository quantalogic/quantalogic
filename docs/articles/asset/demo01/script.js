document.addEventListener('DOMContentLoaded', () => {
  const display = document.querySelector('div.bg-white');
  const buttons = document.querySelectorAll('button');

  let currentInput = '';
  let previousInput = '';
  let operation = null;

  buttons.forEach(button => {
    button.addEventListener('click', () => {
      const value = button.textContent;

      if (value === 'C') {
        currentInput = '';
        previousInput = '';
        operation = null;
        display.textContent = '0';
      } else if (value === '=') {
        if (operation && previousInput && currentInput) {
          const result = calculate(previousInput, currentInput, operation);
          display.textContent = result;
          currentInput = result;
          previousInput = '';
          operation = null;
        }
      } else if (['+', '-', '×', '÷'].includes(value)) {
        if (currentInput === '') return;
        if (previousInput !== '') {
          const result = calculate(previousInput, currentInput, operation);
          display.textContent = result;
          previousInput = result;
        } else {
          previousInput = currentInput;
        }
        currentInput = '';
        operation = value;
      } else {
        if (value === '.' && currentInput.includes('.')) return;
        currentInput += value;
        display.textContent = currentInput;
      }
    });
  });

  function calculate(a, b, op) {
    a = parseFloat(a);
    b = parseFloat(b);
    switch (op) {
      case '+': return a + b;
      case '-': return a - b;
      case '×': return a * b;
      case '÷': return a / b;
      default: return 0;
    }
  }
});