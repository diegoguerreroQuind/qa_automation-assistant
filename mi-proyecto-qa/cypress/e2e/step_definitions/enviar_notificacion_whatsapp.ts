import { Given, When, Then } from "@badeball/cypress-cucumber-preprocessor";

Given("que tengo los datos base para la peticion de enviar notificacion Whatsapp", () => {
    const baseBody = {
        contextSource: "ZER",
        subAccountId: "11834639",
        shippingMethods: [
            {
                channel: "WHATSAPP",
                phoneNumber: "573017831189",
                templateName: "interoperability_adhoc_parkingmeter_download_the_app_wp",
                templateParams: [   
                    "HDS910",
                    "Pablo CAR",
                    "1400"
                ]
            }
        ]
    };
    
    const baseUrl = Cypress.env("url-host-marketing-notification") || "";
    const endpointUrl = `${baseUrl}/marketing-notifications/api/v1/notifications`;

    cy.wrap(baseBody).as("requestBody");
    cy.wrap(endpointUrl).as("requestUrl");
});

Given("ajusto la peticion de enviar notificacion Whatsapp para el caso sin subAccountId", () => {
    cy.get("@requestBody").then((body: any) => {
        delete body.subAccountId;
        cy.wrap(body).as("requestBody");
    });
});

Given("ajusto la peticion de enviar notificacion Whatsapp para el caso happy path", () => {
    cy.log("Los datos base ya son validos para el happy path");
});

When("envio la peticion hacia enviar notificacion Whatsapp", () => {
    cy.get("@requestUrl").then((url: any) => {
        cy.get("@requestBody").then((body: any) => {
            cy.request({
                method: "POST",
                url: url,
                body: body,
                failOnStatusCode: false
            }).as("response");
        });
    });
});

Then("el codigo de respuesta de enviar notificacion Whatsapp debe ser 400", () => {
    cy.get("@response").its("status").should("eq", 400);
});

Then("el codigo de respuesta de enviar notificacion Whatsapp debe ser 200", () => {
    cy.get("@response").its("status").should("eq", 200);
});