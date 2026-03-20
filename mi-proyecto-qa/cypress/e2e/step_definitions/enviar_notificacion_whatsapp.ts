import { Given, When, Then } from "@badeball/cypress-cucumber-preprocessor";

Given("que tengo los datos para 'enviar notificacion Whatsapp'", () => {
    const requestBody = {
        "contextSource": "ZER",
        "subAccountId": "11834639",
        "shippingMethods": [
            {
                "channel": "WHATSAPP",
                "phoneNumber": "573017831189",
                "templateName": "interoperability_adhoc_parkingmeter_download_the_app_wp",
                "templateParams": [   
                    "HDS910","Pablo CAR","1400"
                ]
            }
        ]
    };
    cy.wrap(requestBody).as('requestBody');
});

When("envío la petición hacia 'enviar notificacion Whatsapp'", () => {
    cy.get('@requestBody').then((requestBody) => {
        cy.request({
            method: 'POST',
            url: `${Cypress.env('url-host-marketing-notification')}/marketing-notifications/api/v1/notifications`,
            headers: {},
            body: requestBody,
            failOnStatusCode: false
        }).as('apiResponse');
    });
});

Then("el código de respuesta para 'enviar notificacion Whatsapp' debe ser exitoso", () => {
    cy.get('@apiResponse').then((response: any) => {
        expect(response.status).to.be.oneOf([200, 201, 202, 204]);
    });
});