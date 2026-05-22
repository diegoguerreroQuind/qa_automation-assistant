import { Given, When, Then } from "@badeball/cypress-cucumber-preprocessor";

let requestBody: any;
let response: Cypress.Response<any>;

Given("que tengo los datos base para la peticion de enviar notificacion Whatsapp", () => {
    requestBody = {
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
});

Given("ajusto la peticion de enviar notificacion Whatsapp para el caso sin subAccountId", () => {
    delete requestBody.subAccountId;
});

Given("ajusto la peticion de enviar notificacion Whatsapp para el caso happy path", () => {
    // Los datos base ya corresponden al happy path, no se requiere mutacion
});

When("envio la peticion hacia enviar notificacion Whatsapp", () => {
    const baseUrl = Cypress.env("url-host-marketing-notification") || "";
    
    cy.request({
        method: "POST",
        url: `${baseUrl}/marketing-notifications/api/v1/notifications`,
        headers: {},
        body: requestBody,
        failOnStatusCode: false
    }).then((res) => {
        response = res;
    });
});

Then("el codigo de respuesta de enviar notificacion Whatsapp debe ser 400", () => {
    expect(response.status).to.eq(400);
});

Then("el codigo de respuesta de enviar notificacion Whatsapp debe ser 200", () => {
    expect(response.status).to.eq(200);
});