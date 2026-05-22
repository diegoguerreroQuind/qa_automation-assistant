Feature: Probar enviar notificacion Whatsapp

  Scenario: Notificacion WhatsApp sin subAccountId
    Given que tengo los datos base para la peticion de enviar notificacion Whatsapp
    And ajusto la peticion de enviar notificacion Whatsapp para el caso sin subAccountId
    When envio la peticion hacia enviar notificacion Whatsapp
    Then el codigo de respuesta de enviar notificacion Whatsapp debe ser 400

  Scenario: Happy path notificacion por WhatsApp
    Given que tengo los datos base para la peticion de enviar notificacion Whatsapp
    And ajusto la peticion de enviar notificacion Whatsapp para el caso happy path
    When envio la peticion hacia enviar notificacion Whatsapp
    Then el codigo de respuesta de enviar notificacion Whatsapp debe ser 200