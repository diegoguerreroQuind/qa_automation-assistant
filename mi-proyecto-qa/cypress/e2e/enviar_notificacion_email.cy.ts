describe('Marketing Notifications API', () => {
  it('should successfully execute request: enviar notificacion Email', () => {
    const requestBody = {
      "contextSource": "CONTEXTO",
      "subAccountId": "12345",
      "shippingMethods": [
        {
          "channel": "EMAIL",
          "subject": "Córreo fácil - @#$%^&*()_+1234567890-=¿¡?<>:{}|[];./\\¬° ",
          "message": "T3xt0_Prueb@_UAT_2025!!! ¿Funciona? Sí=TalVez/No*Quizá#%&$<>[]{},.;:-_+|~^`\nPrueba_con_espacios   y    tabulaciones\t⇨✓✗⚡☢ ©®™∞≈≠≤≥µπΩ\nLorem!@#$%^&*()_+1234567890-=¿¡?<>:{}|[];./\\¬°•¶§…«»∆√∑∫∂\nCadena_muy_larga_para_testear_validaciones__________________________\n██████████████████ prueba unicode ██████████████████",
          "emails": [
            "daniel.mejia@quind.io"
          ],
          "attachmentKeys": [
            "1315/facturas/laFactura/305292_1315_20250225.pdf"
          ]
        }
      ]
    };

    cy.request({
      method: 'POST',
      url: `${Cypress.env('url-host-marketing-notification')}/marketing-notifications/api/v1/notifications`,
      headers: {},
      body: requestBody,
      failOnStatusCode: false
    }).then((response: Cypress.Response<any>) => {
      expect(response.status).to.be.oneOf([200, 201]);
      expect(response.body).to.not.be.undefined;
    });
  });
});