export const getErrorMessage = (err) => {
  if (!err) return "Unknown error";

  const statusCode = err.response?.status;
  let backendMsg = err.response?.data?.detail || err.response?.data?.message || err.response?.data;

  let msg = err.message || "An error occurred";

  if (backendMsg) {
    if (typeof backendMsg === "string") {
      msg = backendMsg;
    } else if (Array.isArray(backendMsg)) {
      msg = backendMsg.map(e => {
        if (e.loc && e.msg) {
          const field = e.loc[e.loc.length - 1];
          return `${field}: ${e.msg}`;
        }
        return e.msg || JSON.stringify(e);
      }).join(", ");
    } else if (typeof backendMsg === "object") {
      msg = backendMsg.message || backendMsg.detail || JSON.stringify(backendMsg);
    }
  }

  return msg;
};
