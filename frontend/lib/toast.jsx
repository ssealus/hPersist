// lib/toast.jsx — `<ToastProvider>` at app root, `useToast()` inside screens.

const ToastCtx = React.createContext({ push: () => {} });

function ToastProvider({ children }) {
  const [toasts, setToasts] = React.useState([]);
  const push = React.useCallback((msg, kind = "info") => {
    const id = Math.random().toString(36).slice(2, 8);
    setToasts(t => [...t, { id, msg, kind }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3200);
  }, []);
  return (
    <ToastCtx.Provider value={{ push }}>
      {children}
      <div className="toasts">
        {toasts.map(t => (
          <div key={t.id} className={"toast " + t.kind}>
            <span className={"dot " + t.kind} />
            <span>{t.msg}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

const useToast = () => React.useContext(ToastCtx);
