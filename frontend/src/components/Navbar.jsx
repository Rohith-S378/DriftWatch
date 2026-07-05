import { Link } from "react-router-dom";

function Navbar() {
  return (
    <div className="glass-card p-4 mb-4 flex flex-wrap gap-4">
      <Link to="/" className="text-muted hover:text-primary transition-colors">
        Overview
      </Link>
      <Link to="/insights" className="text-muted hover:text-primary transition-colors">
        Insights
      </Link>
      <Link to="/changes" className="text-muted hover:text-primary transition-colors">
        Changes
      </Link>
      <Link to="/ask" className="text-muted hover:text-primary transition-colors">
        Ask AI
      </Link>
    </div>
  );
}

export default Navbar;