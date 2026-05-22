Feature: Probar enviar notificacion Email

  Scenario: Notificacion por email sin campo emails
    Given que tengo los datos base para la peticion de enviar notificacion Email
    And ajusto la peticion de enviar notificacion Email para el caso sin campo emails
    When envio la peticion hacia enviar notificacion Email
    Then el codigo de respuesta de enviar notificacion Email debe ser 200

  Scenario: Notificacion por email con channel invalido
    Given que tengo los datos base para la peticion de enviar notificacion Email
    And ajusto la peticion de enviar notificacion Email para el caso channel invalido
    When envio la peticion hacia enviar notificacion Email
    Then el codigo de respuesta de enviar notificacion Email debe ser 500

  Scenario: Happy path notificacion por email
    Given que tengo los datos base para la peticion de enviar notificacion Email
    And ajusto la peticion de enviar notificacion Email para el caso happy path
    When envio la peticion hacia enviar notificacion Email
    Then el codigo de respuesta de enviar notificacion Email debe ser 200