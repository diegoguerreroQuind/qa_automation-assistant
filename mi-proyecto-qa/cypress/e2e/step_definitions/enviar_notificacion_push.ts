import { Given, When, Then } from "@badeball/cypress-cucumber-preprocessor";

Given("que tengo los datos base para la peticion de enviar notificacion Push", () => {
    const baseBody = {
        contextSource: "ZER",
        flyKey: "ADE748",
        subAccountId: "40378",
        shippingMethods: [
            {
                channel: "PUSH",  
                title: "Notificación PUSH",
                body: "Este es un mensaje de prueba para Push, #$%&/-+@_",
                image: "https://media.istockphoto.com/id/1674601384/es/foto/mujer-de-negocios-madura-que-busca-un-holograma-en-la-oficina.jpg?s=1024x1024&w=is&k=20&c=9P6v1czgmDZAtyA7voi4GzmwoKr24POqL2EIzu06RZ4=",
                data: {
                    to: "parkingmeterCompleteTransaction",
                    amount: 1000,
                    approvePath: "https://test.services.flypass.co/parkingmeter/api/v1/transactions/approve/true",
                    disapprovePath: "https://test.services.flypass.co/parkingmeter/api/v1/transactions/approve/false",
                    transactionId: "test_COS039_58",
                    stationId: "15",
                    completeTransaction: false
                }
            }
        ]
    };
    cy.wrap(baseBody).as("requestBody");
});

Given("ajusto la peticion de enviar notificacion Push para el caso sin subAccountId vacio o no enviado", () => {
    cy.get("@requestBody").then((body: any) => {
        delete body.subAccountId;
        cy.wrap(body).as("requestBody");
    });
});

Given("ajusto la peticion de enviar notificacion Push para el caso con subAccountId no numerico caracteres alfabeticos", () => {
    cy.get("@requestBody").then((body: any) => {
        body.subAccountId = "ABCDEF";
        cy.wrap(body).as("requestBody");
    });
});

When("envio la peticion hacia enviar notificacion Push", () => {
    cy.get("@requestBody").then((body) => {
        const baseUrl = Cypress.env("url-host-marketing-notification") || "";
        cy.request({
            method: "POST",
            url: `${baseUrl}/marketing-notifications/api/v1/notifications`,
            headers: {},
            body: body,
            failOnStatusCode: false
        }).as("response");
    });
});

Then("el codigo de respuesta de enviar notificacion Push debe ser 400", () => {
    cy.get("@response").then((response: any) => {
        expect(response.status).to.eq(400);
    });
});