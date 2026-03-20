import { Given, When, Then } from "@badeball/cypress-cucumber-preprocessor";

Given("que tengo los datos para 'enviar notificacion Email'", () => {
    const requestBody = {
        "contextSource": "CONTEXTO",
        "subAccountId": "12345",
        "shippingMethods": [
            {
                "channel": "EMAIL",
                "subject": "Córreo fácil - @#$%^&*()_+1234567890-=¿¡?<>:{}|[];./\\\\¬° ",
                "message": "T3xt0_Prueb@_UAT_2025!!! ¿Funciona? Sí=TalVez/No*Quizá#%&$<>[]{},.;:-_+|~^`\nPrueba_con_espacios   y    tabulaciones\t⇨✓✗⚡☢ ©®™∞≈≠≤≥µπΩ\nLorem!@#$%^&*()_+1234567890-=¿¡?<>:{}|[];./\\\\¬°•¶§…«»∆√∑∫∂\nCadena_muy_larga_para_testear_validaciones__________________________\n██████████████████ prueba unicode ██████████████████",
                "emails": ["daniel.mejia@quind.io"],
                "attachmentKeys": [
                    "1315/facturas/laFactura/305292_1315_20250225.pdf"
                ]
            }
        ]
    };
    
    cy.wrap(requestBody).as('bodyEnviarNotificacionEmail');
});

When("envío la petición hacia 'enviar notificacion Email'", () => {
    cy.get('@bodyEnviarNotificacionEmail').then((requestBody) => {
        cy.request({
            method: 'POST',
            url: `${Cypress.env('url-host-marketing-notification')}/marketing-notifications/api/v1/notifications`,
            headers: {},
            body: requestBody,
            failOnStatusCode: false
        }).as('responseEnviarNotificacionEmail');
    });
});

Then("el código de respuesta para 'enviar notificacion Email' debe ser exitoso", () => {
    cy.get('@responseEnviarNotificacionEmail').then((response: any) => {
        expect(response.status).to.be.within(200, 299);
    });
});