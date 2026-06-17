window.sddTemplateForms = {
  read(selector) {
    const form = document.querySelector(selector);
    return form ? Object.fromEntries(new FormData(form).entries()) : {};
  }
};
