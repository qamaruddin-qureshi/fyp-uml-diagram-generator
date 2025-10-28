/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,jsx}',
    './src/components/**/*.{js,jsx}',
    './src/app/**/*.{js,jsx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: '#ffffff',      // White
        secondary: '#ffffff',    // Card background (white)
        accent: '#001f3f',       // Navy Blue
        background: '#f0f4f8',   // Light background
        'muted-text': '#666666', // Muted text
        'border-color': '#001f3f', // Navy Blue borders
      },
      fontSize: {
        // Standard web sizes with improved visibility
        xs: '11px',
        sm: '12px',
        base: '14px',   // Body text
        lg: '16px',     // Labels & secondary text
        xl: '18px',     // Card headings
        '2xl': '20px',  // Section headings
        '3xl': '24px',  // Page headings
        '4xl': '28px',
        '5xl': '32px',
        '6xl': '36px',
      },
      spacing: {
        // Standard web spacing with slight increase
        0: '0px',
        1: '4px',
        2: '8px',
        3: '12px',
        4: '16px',
        5: '20px',
        6: '24px',
        8: '32px',
        10: '40px',
        12: '48px',
      },
      borderRadius: {
        'lg': '8px',
        'md': '6px',
        'sm': '4px',
      },
    },
  },
  plugins: [],
}
