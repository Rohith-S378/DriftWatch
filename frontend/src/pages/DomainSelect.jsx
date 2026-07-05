import { useNavigate } from "react-router-dom";

function DomainSelect() {
  const navigate = useNavigate();

  const handleSelect = (domain) => {
    localStorage.setItem("domain", domain);
    navigate("/overview");
  };

  return (
    <div className="min-h-[90vh] p-8">
      <h1 className="text-3xl font-bold mb-6 text-center">Select Your Domain</h1>

      <div className="flex flex-col items-center gap-4">
        <button
          onClick={() => handleSelect("Competitive Exams")}
          className="btn btn-primary w-[200px] py-3"
        >
          Competitive Exams
        </button>

        <button
          onClick={() => handleSelect("Technical Courses")}
          className="btn btn-primary w-[200px] py-3"
        >
          Technical Courses
        </button>

        <button
          onClick={() => handleSelect("Schools & Colleges")}
          className="btn btn-primary w-[200px] py-3"
        >
          Schools & Colleges
        </button>
      </div>
    </div>
  );
}

export default DomainSelect;