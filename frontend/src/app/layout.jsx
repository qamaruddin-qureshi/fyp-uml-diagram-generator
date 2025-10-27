import './globals.css'
import Navbar from '@/components/Navbar'

export const metadata = {
  title: 'UML Diagram Generator',
  description: 'Generate UML diagrams from user stories using AI',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <Navbar />
        <main>{children}</main>
      </body>
    </html>
  )
}
