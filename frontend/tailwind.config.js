export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        prime: {
          black: '#08090D', panel: '#11131A', panel2: '#0D0E14', gold: '#D4AF37', softGold: '#F3D77A', red: '#8B0000', brightRed: '#D72638', green: '#22C55E', amber: '#F59E0B'
        }
      },
      fontFamily: {
        mono: ['Share Tech Mono', 'monospace'],
        display: ['Orbitron', 'sans-serif']
      }
    }
  },
  plugins: []
}
