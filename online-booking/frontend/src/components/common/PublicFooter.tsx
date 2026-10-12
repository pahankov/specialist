import { Link } from 'react-router-dom';
import './PublicFooter.css';

/** Public footer: legal links + copyright holder. */
function PublicFooter() {
  return (
    <footer className="public-footer">
      <span>© 2026 Ковалевский Павел Юрьевич · Все права защищены</span>
      <span className="public-footer-links">
        <Link to="/offer">Оферта</Link>
        {' · '}
        <Link to="/privacy">Политика обработки ПДн</Link>
      </span>
    </footer>
  );
}

export default PublicFooter;
