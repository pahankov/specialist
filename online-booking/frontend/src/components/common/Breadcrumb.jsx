import { Link } from 'react-router-dom';
import './SharedComponents.css';

export default function Breadcrumb({ items }) {
    if (items.length === 0) return null;

    return (
        <nav className="breadcrumb" aria-label="Навигационная цепочка">
            <Link to="/admin/dashboard" className="breadcrumb-home">🏠</Link>
            {items.map((item, index) => (
                <span className="breadcrumb-item" key={`breadcrumb-${index}`}>
                    <span className="breadcrumb-sep">/</span>
                    {index === items.length - 1 ? (
                        <span className="breadcrumb-current">{item.label}</span>
                    ) : (
                        <Link to={item.path}>{item.label}</Link>
                    )}
                </span>
            ))}
        </nav>
    );
}
