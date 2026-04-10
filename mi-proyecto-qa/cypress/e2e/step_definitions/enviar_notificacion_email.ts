import { Given, When, Then } from "@badeball/cypress-cucumber-preprocessor";

Given("que tengo los datos base para la peticion de enviar notificacion Email", () => {
    const basePayload = {
        contextSource: "CONTEXTO",
        subAccountId: "12345",
        shippingMethods: [
            {
                channel: "EMAIL",
                subject: "Córreo fácil - @#$%^&*()_+1234567890-=¿¡?<>:{}|[];./\\¬° ",
                message: "T3xt0_Prueb@_UAT_2025!!! ¿Funciona? Sí=TalVez/No*Quizá#%&$<>[]{},.;:-_+|~^`\nPrueba_con_espacios   y    tabulaciones\t⇨✓✗⚡☢ ©®™∞≈≠≤≥µπΩ\nLorem!@#$%^&*()_+1234567890-=¿¡?<>:{}|[];./\\¬°•¶§…«»∆√∑∫∂\nCadena_muy_larga_para_testear_validaciones__________________________\n██████████████████ prueba unicode ██████████████████",
                emails: ["daniel.mejia@quind.io"],
                attachmentKeys: [
                    "1315/facturas/laFactura/305292_1315_20250225.pdf"
                ]
            }
        ]
    };
    cy.wrap(basePayload).as("requestBody");
});

Given("ajusto la peticion de enviar notificacion Email para el caso sin campo emails o enviado vacio", () => {
    cy.get("@requestBody").then((payload: any) => {
        payload.shippingMethods[0].emails = [];
        cy.wrap(payload).as("requestBody");
    });
});

Given("ajusto la peticion de enviar notificacion Email para el caso con channel invalido", () => {
    cy.get("@requestBody").then((payload: any) => {
        payload.shippingMethods[0].channel = "INVALIDO";
        cy.wrap(payload).as("requestBody");
    });
});

Given("ajusto la peticion de enviar notificacion Email para el caso happy path", () => {
    cy.log("Mantenemos el payload original para el happy path");
});

When("envio la peticion hacia enviar notificacion Email", () => {
    cy.get("@requestBody").then((payload: any) => {
        const baseUrl = Cypress.env("url-host-marketing-notification") || "";
        cy.request({
            method: "POST",
            url: `${baseUrl}/marketing-notifications/api/v1/notifications`,
            headers: {},
            body: payload,
            failOnStatusCode: false
        }).as("apiResponse");
    });
});

Then("el codigo de respuesta de enviar notificacion Email debe ser 200", () => {
    cy.get("@apiResponse").then((response: any) => {
        expect(response.status).to.eq(200);
    });
});

Then("el codigo de respuesta de enviar notificacion Email debe ser 500", () => {
    cy.get("@apiResponse").then((response: any) => {
        expect(response.status).to.eq(500);
    });
});