import { Given, When, Then } from "@badeball/cypress-cucumber-preprocessor";

Given("que tengo los datos base para la peticion de enviar notificacion Email", () => {
    const baseUrl = Cypress.env("url-host-marketing-notification") || "http://localhost";
    const requestUrl = `${baseUrl}/marketing-notifications/api/v1/notifications`;
    
    const requestBody = {
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

    cy.wrap(requestUrl).as("requestUrl");
    cy.wrap(requestBody).as("requestBody");
});

Given("ajusto la peticion de enviar notificacion Email para el caso sin campo emails", () => {
    cy.get("@requestBody").then((body: any) => {
        delete body.shippingMethods[0].emails;
        cy.wrap(body).as("requestBody");
    });
});

Given("ajusto la peticion de enviar notificacion Email para el caso channel invalido", () => {
    cy.get("@requestBody").then((body: any) => {
        body.shippingMethods[0].channel = "INVALIDO";
        cy.wrap(body).as("requestBody");
    });
});

Given("ajusto la peticion de enviar notificacion Email para el caso happy path", () => {
    cy.log("Los datos base ya están configurados para el happy path");
});

When("envio la peticion hacia enviar notificacion Email", () => {
    cy.get("@requestUrl").then((url: any) => {
        cy.get("@requestBody").then((body: any) => {
            cy.request({
                method: "POST",
                url: url,
                body: body,
                headers: {
                    "Content-Type": "application/json"
                },
                failOnStatusCode: false
            }).as("response");
        });
    });
});

Then("el codigo de respuesta de enviar notificacion Email debe ser 200", () => {
    cy.get("@response").its("status").should("eq", 200);
});

Then("el codigo de respuesta de enviar notificacion Email debe ser 500", () => {
    cy.get("@response").its("status").should("eq", 500);
});