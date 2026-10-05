// Separate file (not inline) so the page can use a strict Content-Security-Policy: script-src 'self'.
window.ui = SwaggerUIBundle({
  url: "/openapi.json",
  dom_id: "#swagger-ui",
  persistAuthorization: true,
  displayRequestDuration: true,
  tryItOutEnabled: false
});
